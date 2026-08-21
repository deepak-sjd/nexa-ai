from google import genai

from app.core.config import settings


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
    # CREATE SINGLE EMBEDDING
    # ============================================================

    def embed_text(self, text: str) -> list[float]:
        """
        Convert one piece of text into an embedding vector.
        """

        if not text or not text.strip():
            return []

        response = self.client.models.embed_content(
            model=self.model,
            contents=text,
        )

        if not response.embeddings:
            return []

        return response.embeddings[0].values

    # ============================================================
    # CREATE MULTIPLE EMBEDDINGS
    # ============================================================

    def embed_documents(
        self,
        documents: list[str],
    ) -> list[list[float]]:
        """
        Convert multiple document chunks into embeddings.
        """

        embeddings = []

        for document in documents:

            if not document or not document.strip():
                continue

            embedding = self.embed_text(
                document
            )

            if embedding:
                embeddings.append(
                    embedding
                )

        return embeddings

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