from dataclasses import dataclass
from typing import Any

from backend.app.rag.embeddings import embedding_service



# ============================================================
# RETRIEVAL RESULT
# ============================================================

@dataclass
class RetrievalResult:
    """
    Represents one piece of knowledge returned by the retriever.
    """

    content: str
    score: float

    metadata: dict[str, Any]


# ============================================================
# RETRIEVER
# ============================================================

class Retriever:
    """
    Semantic retriever for the NEXA AI RAG pipeline.

    Responsibilities:
        1. Convert user query into an embedding.
        2. Search the vector store.
        3. Calculate/obtain similarity scores.
        4. Apply minimum relevance filtering.
        5. Return the most relevant chunks.

    The actual vector database is intentionally kept separate.
    This allows us to later use PostgreSQL + pgvector, Qdrant,
    or another production vector database without changing
    the rest of the RAG pipeline.
    """

    def __init__(
        self,
        vector_store=None,
        top_k: int = 8,
        similarity_threshold: float = 0.35,
    ):
        self.vector_store = vector_store

        self.top_k = max(
            1,
            top_k,
        )

        self.similarity_threshold = max(
            0.0,
            min(similarity_threshold, 1.0),
        )

    # ========================================================
    # QUERY EMBEDDING
    # ========================================================

    def _create_query_embedding(
        self,
        query: str,
    ) -> list[float]:

        if not query or not query.strip():
            return []

        return embedding_service.embed_query(
            query.strip()
        )

    # ========================================================
    # VECTOR SEARCH
    # ========================================================

    def _search_vector_store(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:

        if self.vector_store is None:
            raise RuntimeError(
                "Vector store is not configured."
            )

        if not query_embedding:
            return []

        """
        The vector store must expose:

            search(
                embedding=query_embedding,
                top_k=top_k
            )

        Expected result format:

            [
                {
                    "content": "...",
                    "score": 0.87,
                    "metadata": {...}
                }
            ]
        """

        results = self.vector_store.search(
            embedding=query_embedding,
            top_k=top_k,
        )

        if not results:
            return []

        return results

    # ========================================================
    # NORMALIZE RESULTS
    # ========================================================

    def _normalize_results(
        self,
        results: list[dict[str, Any]],
    ) -> list[RetrievalResult]:

        normalized = []

        for result in results:

            content = str(
                result.get("content", "")
            ).strip()

            if not content:
                continue

            try:
                score = float(
                    result.get("score", 0.0)
                )
            except (
                TypeError,
                ValueError,
            ):
                score = 0.0

            metadata = result.get(
                "metadata",
                {},
            )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            normalized.append(
                RetrievalResult(
                    content=content,
                    score=score,
                    metadata=metadata,
                )
            )

        return normalized

    # ========================================================
    # RELEVANCE FILTER
    # ========================================================

    def _filter_by_relevance(
        self,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:

        return [
            result
            for result in results
            if result.score
            >= self.similarity_threshold
        ]

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    def _remove_duplicates(
        self,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:

        seen = set()

        unique_results = []

        for result in results:

            # Prefer chunk ID when available.
            chunk_id = result.metadata.get(
                "chunk_id"
            )

            if chunk_id is not None:
                duplicate_key = (
                    "chunk_id",
                    str(chunk_id),
                )
            else:
                duplicate_key = (
                    "content",
                    result.content,
                )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            unique_results.append(
                result
            )

        return unique_results

    # ========================================================
    # SORT RESULTS
    # ========================================================

    def _sort_results(
        self,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:

        return sorted(
            results,
            key=lambda result: result.score,
            reverse=True,
        )

    # ========================================================
    # MAIN RETRIEVAL
    # ========================================================

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve the most relevant knowledge for a query.
        """

        query = query.strip()

        if not query:
            return []

        requested_top_k = (
            top_k
            if top_k is not None
            else self.top_k
        )

        requested_top_k = max(
            1,
            requested_top_k,
        )

        # ----------------------------------------------------
        # 1. Convert query → embedding
        # ----------------------------------------------------

        query_embedding = (
            self._create_query_embedding(
                query
            )
        )

        if not query_embedding:
            return []

        # ----------------------------------------------------
        # 2. Search vector database
        #
        # Retrieve extra candidates because filtering
        # and deduplication may remove some results.
        # ----------------------------------------------------

        candidate_count = max(
            requested_top_k * 3,
            requested_top_k + 5,
        )

        raw_results = (
            self._search_vector_store(
                query_embedding=query_embedding,
                top_k=candidate_count,
            )
        )

        # ----------------------------------------------------
        # 3. Normalize
        # ----------------------------------------------------

        results = self._normalize_results(
            raw_results
        )

        # ----------------------------------------------------
        # 4. Relevance filtering
        # ----------------------------------------------------

        results = self._filter_by_relevance(
            results
        )

        # ----------------------------------------------------
        # 5. Remove duplicate chunks
        # ----------------------------------------------------

        results = self._remove_duplicates(
            results
        )

        # ----------------------------------------------------
        # 6. Sort by similarity
        # ----------------------------------------------------

        results = self._sort_results(
            results
        )

        # ----------------------------------------------------
        # 7. Return final top-K
        # ----------------------------------------------------

        return results[
            :requested_top_k
        ]


# ============================================================
# SHARED RETRIEVER INSTANCE
# ============================================================

retriever = Retriever(
    top_k=8,
    similarity_threshold=0.35,
)
