import base64

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
)

from app.core.config import settings
from app.core.logging_config import get_logger


logger = get_logger(__name__)


class ImageGenerationQuotaExceededError(RuntimeError):
    """
    Raised when the image generation API's rate limit is hit
    and bounded retries have been exhausted.

    Carries a short, user-facing message only.
    """


class ImageGenerationError(RuntimeError):
    """
    Raised for any other image generation failure (invalid
    prompt, safety block, no image returned, etc).
    """


def _is_retryable(exception: BaseException) -> bool:
    """
    Only retry on rate limits / transient server errors —
    never on things like a safety-blocked prompt, which will
    just fail the same way again.
    """

    if isinstance(exception, genai_errors.ClientError):
        return exception.code == 429

    if isinstance(exception, genai_errors.ServerError):
        return True

    return False


class ImageService:
    """
    Handles image generation via Gemini's image-capable model.

    Responsible ONLY for talking to the image generation API.
    Does not persist images to disk or a database — returns
    raw bytes for the caller (the API route) to decide what to
    do with.
    """

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

        self.model = settings.gemini_image_model

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(2),
        reraise=True,
    )
    def _generate(self, prompt: str):
        return self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["Text", "Image"],
            ),
        )

    def generate_image(
        self,
        prompt: str,
    ) -> dict:
        """
        Generate an image from a text prompt.

        Returns
        -------
        dict with:
            image_base64: str — base64-encoded image bytes
            mime_type: str — e.g. "image/png"
            text: str | None — any accompanying text Gemini
                returned alongside the image (often a short
                caption or description)
        """

        if not prompt or not prompt.strip():
            raise ImageGenerationError(
                "Please describe the image you want generated."
            )

        try:
            response = self._generate(prompt.strip())
        except genai_errors.ClientError as e:
            if e.code == 429:
                logger.warning(
                    "Image generation quota hit: %s", e
                )
                raise ImageGenerationQuotaExceededError(
                    "The image generation service is "
                    "temporarily rate-limited. Please try "
                    "again in a minute."
                ) from e

            logger.error(
                "Image generation client error: %s", e
            )
            raise ImageGenerationError(
                "Could not generate that image. Try "
                "rephrasing your request."
            ) from e
        except genai_errors.ServerError as e:
            logger.error(
                "Image generation server error: %s", e
            )
            raise ImageGenerationError(
                "The image generation service is "
                "temporarily unavailable. Please try again."
            ) from e

        candidates = getattr(response, "candidates", None)

        if not candidates:
            raise ImageGenerationError(
                "No image was returned. Try rephrasing your "
                "request."
            )

        parts = getattr(candidates[0].content, "parts", None) or []

        image_bytes: bytes | None = None
        mime_type = "image/png"
        text_response: str | None = None

        for part in parts:

            inline_data = getattr(part, "inline_data", None)

            if inline_data is not None:
                image_bytes = inline_data.data
                mime_type = (
                    getattr(inline_data, "mime_type", None)
                    or "image/png"
                )
                continue

            part_text = getattr(part, "text", None)

            if part_text:
                text_response = part_text

        if image_bytes is None:
            # The model responded but didn't include an image —
            # usually means the prompt was blocked or refused.
            raise ImageGenerationError(
                text_response
                or "No image was generated for that prompt. "
                "It may have been blocked by content safety "
                "filters — try rephrasing."
            )

        return {
            "image_base64": base64.b64encode(
                image_bytes
            ).decode("utf-8"),
            "mime_type": mime_type,
            "text": text_response,
        }


# ============================================================
# SHARED SERVICE INSTANCE
# ============================================================

image_service = ImageService()