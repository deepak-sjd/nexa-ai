from google import genai
from google.genai import errors as genai_errors
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging_config import get_logger


logger = get_logger(__name__)


# Gemini's free-tier embedding quota is small and shared across
# the whole app, so keep batches modest and retries bounded —
# per the project's own rule: never retry indefinitely.
EMBED_BATCH_SIZE = 20

# Never wait longer than this for a single retry, even if the
# provider asks for more — this endpoint is synchronous and a
# caller shouldn't be blocked for minutes.
MAX_RETRY_WAIT_SECONDS = 45


class EmbeddingQuotaExceededError(RuntimeError):
    """
    Raised when the embedding API's rate limit is hit and
    bounded retries have been exhausted.

    Carries a short, user-facing message — never the raw
    provider error payload (that's logged separately).
    """


def _is_retryable(exception: BaseException) -> bool:
    """
    Only retry on rate limits / transient server errors.
    Never retry on things like invalid input — retrying those
    just wastes quota for a guaranteed repeat failure.
    """

    if isinstance(exception, genai_errors.ClientError):
        return exception.code == 429

    if isinstance(exception, genai_errors.ServerError):
        return True

    return False


def _extract_retry_delay_seconds(
    exception: BaseException,
) -> float | None:
    """
    Gemini's 429 responses include the server's own suggested
    wait time (e.g. "Please retry in 39s"), structured as a
    RetryInfo detail. Respecting this — instead of a generic
    fixed backoff — is far more likely to actually succeed on
    retry, since our own backoff schedule has no relationship
    to when the provider's rate-limit window actually resets.
    """

    if not isinstance(exception, genai_errors.ClientError):
        return None

    try:
        details = (
            exception.details.get("error", {}).get("details", [])
        )
    except AttributeError:
        return None

    for detail in details:
        type_name = detail.get("@type", "")

        if not type_name.endswith("RetryInfo"):
            continue

        delay_text = detail.get("retryDelay", "")

        if delay_text.endswith("s"):
            try:
                return float(delay_text[:-1])
            except ValueError:
                return None

    return None


def _wait_for_gemini_or_backoff(retry_state):
    """
    Tenacity wait strategy: use the provider's own suggested
    retryDelay when available (capped at MAX_RETRY_WAIT_SECONDS),
    falling back to exponential backoff otherwise.
    """

    exception = retry_state.outcome.exception()

    suggested_delay = (
        _extract_retry_delay_seconds(exception)
        if exception
        else None
    )

    if suggested_delay is not None:
        capped_delay = min(
            suggested_delay,
            MAX_RETRY_WAIT_SECONDS,
        )

        logger.info(
            "Waiting %.0fs before retry, as suggested by "
            "the embedding API (capped at %ds).",
            capped_delay,
            MAX_RETRY_WAIT_SECONDS,
        )

        return capped_delay

    # Fall back to standard exponential backoff for errors
    # that don't carry a suggested delay (e.g. ServerError).
    fallback = wait_exponential(multiplier=2, min=2, max=20)

    return fallback(retry_state)


class EmbeddingService:
    """
    Converts text into numerical embedding vectors.

    These vectors will later be used by the RAG retriever
    to find documents that are semantically similar
    to the user's question.
    """

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

        # Gemini embedding model
        self.model = "gemini-embedding-001"

    # ============================================================
    # LOW-LEVEL CALL WITH BOUNDED RETRY
    # ============================================================

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=_wait_for_gemini_or_backoff,
        stop=stop_after_attempt(2),
        reraise=True,
    )
    def _embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        try:
            response = self.client.models.embed_content(
                model=self.model,
                contents=texts,
            )
        except genai_errors.ClientError as e:
            if e.code == 429:
                logger.warning(
                    "Embedding quota hit (will retry with "
                    "backoff if attempts remain): %s",
                    e,
                )
            raise

        if not response.embeddings:
            return []

        return [
            embedding.values for embedding in response.embeddings
        ]

    # ============================================================
    # CREATE SINGLE EMBEDDING
    # ============================================================

    def embed_text(self, text: str) -> list[float]:
        """
        Convert one piece of text into an embedding vector.
        """

        if not text or not text.strip():
            return []

        try:
            embeddings = self._embed_batch([text])
        except genai_errors.ClientError as e:
            if e.code == 429:
                raise EmbeddingQuotaExceededError(
                    "The embedding service is temporarily "
                    "rate-limited. Please try again in a "
                    "minute."
                ) from e
            raise

        return embeddings[0] if embeddings else []

    # ============================================================
    # CREATE MULTIPLE EMBEDDINGS (REAL BATCHING)
    # ============================================================

    def embed_documents(
        self,
        documents: list[str],
    ) -> list[list[float]]:
        """
        Convert multiple document chunks into embeddings.

        Sends chunks in batches of EMBED_BATCH_SIZE per API
        call (instead of one call per chunk), so a 20-chunk
        document costs 1 request instead of 20 — the main
        fix for hitting the free-tier rate limit.
        """

        non_empty = [
            document
            for document in documents
            if document and document.strip()
        ]

        if not non_empty:
            return []

        all_embeddings: list[list[float]] = []

        for start in range(0, len(non_empty), EMBED_BATCH_SIZE):

            batch = non_empty[start : start + EMBED_BATCH_SIZE]

            try:
                batch_embeddings = self._embed_batch(batch)
            except genai_errors.ClientError as e:
                if e.code == 429:
                    raise EmbeddingQuotaExceededError(
                        "The embedding service is temporarily "
                        "rate-limited after repeated attempts. "
                        "Please try uploading again in a "
                        "minute."
                    ) from e
                raise

            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    # ============================================================
    # EMBED QUERY
    # ============================================================

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        """
        Convert the user's question into an embedding.

        The retriever will compare this vector against
        document vectors to find relevant information.
        """

        return self.embed_text(query)


# ============================================================
# SHARED SERVICE INSTANCE
# ============================================================

embedding_service = EmbeddingService()