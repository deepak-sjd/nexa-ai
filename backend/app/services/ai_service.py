from collections.abc import Generator

from google import genai
from google.genai import types

from app.core.config import settings


class AIService:

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

    # ========================================================
    # SYSTEM INSTRUCTION
    # ========================================================

    SYSTEM_INSTRUCTION = """
You are NEXA AI, a professional and helpful AI assistant.

Rules:
- Be accurate and clear.
- Answer the user's question directly.
- Remember information from the provided conversation history.
- Do not invent personal information about the user.
- If information is not available in the conversation, say that you do not know.
- Keep simple questions concise.
- For technical questions, provide structured explanations.
- Use markdown when it improves readability.
"""

    # ========================================================
    # BUILD CONVERSATION
    # ========================================================

    def _build_prompt(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> str:

        conversation_history = conversation_history or []

        prompt_parts = []

        for message in conversation_history:

            role = message.get("role")
            content = message.get("content", "").strip()

            if not content:
                continue

            if role == "user":
                prompt_parts.append(
                    f"User: {content}"
                )

            elif role == "assistant":
                prompt_parts.append(
                    f"Assistant: {content}"
                )

        prompt_parts.append(
            f"User: {user_message}"
        )

        return "\n\n".join(prompt_parts)

    # ========================================================
    # NORMAL RESPONSE
    # ========================================================

    def generate_response(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> str:

        prompt = self._build_prompt(
            user_message=user_message,
            conversation_history=conversation_history,
        )

        response = self.client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.SYSTEM_INSTRUCTION,
                max_output_tokens=700,
            ),
        )

        return response.text or (
            "I'm sorry, but I couldn't generate a response."
        )

    # ========================================================
    # STREAMING RESPONSE
    # ========================================================

    def generate_response_stream(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> Generator[str, None, None]:

        prompt = self._build_prompt(
            user_message=user_message,
            conversation_history=conversation_history,
        )

        response_stream = (
            self.client.models.generate_content_stream(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    max_output_tokens=700,
                ),
            )
        )

        for chunk in response_stream:

            text = getattr(chunk, "text", None)

            if text:
                yield text


# ============================================================
# SHARED SERVICE INSTANCE
# ============================================================

ai_service = AIService()