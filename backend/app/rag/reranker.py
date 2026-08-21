from dataclasses import dataclass
from typing import Any

from app.rag.retriever import RetrievalResult


@dataclass
class RerankedResult:
    """
    Represents a document chunk after reranking.
    """

    content: str
    score: float
    original_score: float
    metadata: dict[str, Any]


class Reranker:
    """
    Reranks retrieved RAG chunks.

    Current stage:
        - Uses the initial retrieval score.
        - Removes weak candidates.
        - Applies a relevance weighting.
        - Returns the strongest chunks first.

    This interface is intentionally separated so we can
    replace the scoring logic later with a real cross-encoder
    or reranking model without changing the rest of the RAG pipeline.
    """

    def __init__(
        self,
        top_k: int = 5,
        min_score: float = 0.35,
    ):
        self.top_k = max(1, top_k)

        self.min_score = max(
            0.0,
            min(min_score, 1.0),
        )

    # ============================================================
    # RERANK
    # ============================================================

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RerankedResult]:
        """
        Rerank retrieved chunks.

        Args:
            query:
                Original user question.

            results:
                Candidates returned by the retriever.
        """

        if not query or not query.strip():
            return []

        if not results:
            return []

        reranked = []

        for result in results:

            if result.score < self.min_score:
                continue

            # Current baseline:
            # preserve the semantic retrieval score.
            rerank_score = result.score

            reranked.append(
                RerankedResult(
                    content=result.content,
                    score=rerank_score,
                    original_score=result.score,
                    metadata=result.metadata,
                )
            )

        # Highest relevance first
        reranked.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        return reranked[: self.top_k]


# ============================================================
# SHARED RERANKER INSTANCE
# ============================================================

reranker = Reranker(
    top_k=5,
    min_score=0.35,
)