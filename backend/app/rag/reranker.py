"""
==============================================================
NEXA AI
Production-Oriented RAG Reranker
==============================================================

Purpose
-------
Second-stage relevance scoring for retrieved RAG chunks.

Pipeline:

    User Query
        ↓
    Retriever
        ↓
    Candidate Chunks
        ↓
    Reranker
        ↓
    Ranked Chunks
        ↓
    Context Builder
        ↓
    LLM

Current implementation
----------------------
This version provides a production-oriented baseline reranker.

It combines:

1. Semantic retrieval score
2. Query/chunk lexical relevance
3. Exact query-term coverage
4. Duplicate filtering
5. Minimum relevance filtering
6. Deterministic ranking

The class is intentionally isolated so the scoring strategy
can later be replaced with a real cross-encoder or reranking
model without changing the rest of the RAG pipeline.

Important
---------
This is NOT a neural cross-encoder yet.

It is a strong, lightweight baseline designed to work with
the existing FAISS + Retriever architecture without adding
another model/API dependency.

==============================================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.rag.retriever import RetrievalResult


# ==============================================================
# DATA MODEL
# ==============================================================


@dataclass
class RerankedResult:
    """
    Represents a document chunk after second-stage reranking.

    Attributes
    ----------
    content:
        Retrieved document chunk text.

    score:
        Final reranking score.

    original_score:
        Original semantic similarity score returned by the
        Retriever / VectorStore.

    metadata:
        Original chunk metadata.
    """

    content: str
    score: float
    original_score: float
    metadata: dict[str, Any]


# ==============================================================
# RERANKER
# ==============================================================


class Reranker:
    """
    Production-oriented lightweight RAG reranker.

    The reranker does not retrieve documents.

    It receives candidates from the Retriever and calculates
    a second relevance score.

    Scoring strategy
    ----------------

        final_score =
            semantic_weight * semantic_score
            +
            lexical_weight * lexical_score

    Where:

        semantic_score
            = original vector similarity score

        lexical_score
            = query-term relevance inside the chunk

    This gives the system two signals:

        Semantic similarity
            "Does this chunk mean something similar?"

        Lexical relevance
            "Does this chunk actually contain important
             words from the user's question?"

    This is more useful than simply returning the original
    retrieval score.

    Later this class can be replaced internally with:

        CrossEncoder
        BGE Reranker
        Cohere Rerank
        Vertex AI reranking
        Another neural reranking model

    without changing RAGService or ContextBuilder.
    """

    # Common English stop words.

    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "should",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "would",
        "you",
        "your",
    }

    # ----------------------------------------------------------
    # INITIALIZATION
    # ----------------------------------------------------------

    def __init__(
        self,
        top_k: int = 5,
        min_score: float = 0.35,
        semantic_weight: float = 0.75,
        lexical_weight: float = 0.25,
        min_lexical_overlap: float = 0.0,
    ):
        """
        Initialize the reranker.

        Parameters
        ----------
        top_k:
            Maximum number of final chunks.

        min_score:
            Minimum original semantic retrieval score.

        semantic_weight:
            Weight assigned to semantic similarity.

        lexical_weight:
            Weight assigned to lexical relevance.

        min_lexical_overlap:
            Optional minimum lexical overlap required.

            Keep this at 0.0 initially because semantic
            retrieval should still be able to find relevant
            chunks even when exact words are different.
        """

        self.top_k = max(1, int(top_k))

        self.min_score = self._clamp(
            min_score,
            0.0,
            1.0,
        )

        semantic_weight = max(
            0.0,
            float(semantic_weight),
        )

        lexical_weight = max(
            0.0,
            float(lexical_weight),
        )

        total_weight = (
            semantic_weight
            + lexical_weight
        )

        if total_weight <= 0:
            raise ValueError(
                "semantic_weight + lexical_weight "
                "must be greater than zero."
            )

        # Normalize weights so their sum is exactly 1.

        self.semantic_weight = (
            semantic_weight / total_weight
        )

        self.lexical_weight = (
            lexical_weight / total_weight
        )

        self.min_lexical_overlap = self._clamp(
            min_lexical_overlap,
            0.0,
            1.0,
        )

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int | None = None,
    ) -> list[RerankedResult]:
        """
        Rerank retrieved candidates.

        Parameters
        ----------
        query:
            Original user query.

        results:
            Candidates returned by Retriever.

        top_k:
            Optional per-call override.

        Returns
        -------
        list[RerankedResult]
            Strongest chunks first.
        """

        # ------------------------------------------------------
        # Validate query
        # ------------------------------------------------------

        if not query or not query.strip():
            return []

        # ------------------------------------------------------
        # Validate candidates
        # ------------------------------------------------------

        if not results:
            return []

        clean_query = query.strip()

        # ------------------------------------------------------
        # Prepare query tokens once.
        #
        # Avoid repeating tokenization for every candidate.
        # ------------------------------------------------------

        query_tokens = self._tokenize(
            clean_query
        )

        # ------------------------------------------------------
        # Remove duplicates before scoring.
        # ------------------------------------------------------

        unique_results = self._remove_duplicates(
            results
        )

        reranked: list[RerankedResult] = []

        # ------------------------------------------------------
        # Score every candidate.
        # ------------------------------------------------------

        for result in unique_results:

            content = self._clean_content(
                result.content
            )

            if not content:
                continue

            # ----------------------------------------------
            # Original semantic score
            # ----------------------------------------------

            original_score = self._safe_score(
                result.score
            )

            # ----------------------------------------------
            # Weak semantic candidates are removed early.
            # ----------------------------------------------

            if original_score < self.min_score:
                continue

            # ----------------------------------------------
            # Lexical relevance
            # ----------------------------------------------

            lexical_score = (
                self._calculate_lexical_score(
                    query_tokens=query_tokens,
                    content=content,
                )
            )

            # ----------------------------------------------
            # Optional lexical filtering.
            # ----------------------------------------------

            if (
                lexical_score
                < self.min_lexical_overlap
            ):
                continue

            # ----------------------------------------------
            # Final combined score
            # ----------------------------------------------

            final_score = (
                self.semantic_weight
                * original_score
            ) + (
                self.lexical_weight
                * lexical_score
            )

            final_score = self._clamp(
                final_score,
                0.0,
                1.0,
            )

            reranked.append(
                RerankedResult(
                    content=content,
                    score=final_score,
                    original_score=original_score,
                    metadata=self._safe_metadata(
                        result.metadata
                    ),
                )
            )

        # ------------------------------------------------------
        # Deterministic ranking.
        #
        # First:
        #   final reranking score
        #
        # Second:
        #   original semantic score
        #
        # This prevents unstable ordering when final scores
        # are identical.
        # ------------------------------------------------------

        reranked.sort(
            key=lambda item: (
                item.score,
                item.original_score,
            ),
            reverse=True,
        )

        # ------------------------------------------------------
        # Final top-K selection.
        # ------------------------------------------------------

        limit = (
            self.top_k
            if top_k is None
            else max(1, int(top_k))
        )

        return reranked[:limit]

    # ==========================================================
    # LEXICAL SCORING
    # ==========================================================

    def _calculate_lexical_score(
        self,
        query_tokens: set[str],
        content: str,
    ) -> float:
        """
        Calculate lightweight lexical relevance.

        The score represents how much of the meaningful query
        vocabulary is represented inside the document chunk.

        Example:

            Query:
                "How does VectorStore search embeddings?"

            Chunk:
                "VectorStore searches embeddings using FAISS."

        A high percentage of query terms are represented,
        resulting in a stronger lexical score.

        Returns
        -------
        float
            Score between 0.0 and 1.0.
        """

        if not query_tokens:
            return 0.0

        content_tokens = self._tokenize(
            content
        )

        if not content_tokens:
            return 0.0

        matched_tokens = (
            query_tokens
            & content_tokens
        )

        coverage = (
            len(matched_tokens)
            / len(query_tokens)
        )

        # ------------------------------------------------------
        # Small bonus when the complete query phrase appears.
        # ------------------------------------------------------

        normalized_query = self._normalize_text(
            " ".join(sorted(query_tokens))
        )

        normalized_content = self._normalize_text(
            content
        )

        phrase_bonus = 0.0

        if normalized_query and (
            normalized_query
            in normalized_content
        ):
            phrase_bonus = 0.15

        return self._clamp(
            coverage + phrase_bonus,
            0.0,
            1.0,
        )

    # ==========================================================
    # TOKENIZATION
    # ==========================================================

    def _tokenize(
        self,
        text: str,
    ) -> set[str]:
        """
        Convert text into normalized meaningful tokens.

        Stop words are removed so common words do not dominate
        the relevance calculation.
        """

        normalized = self._normalize_text(
            text
        )

        tokens = re.findall(
            r"[a-zA-Z0-9_]+",
            normalized,
        )

        return {
            token
            for token in tokens
            if (
                len(token) > 1
                and token not in self.STOP_WORDS
            )
        }

    # ==========================================================
    # TEXT NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        """
        Normalize text for lexical comparison.
        """

        return " ".join(
            str(text)
            .lower()
            .strip()
            .split()
        )

    # ==========================================================
    # DUPLICATE REMOVAL
    # ==========================================================

    def _remove_duplicates(
        self,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Remove duplicate chunks.

        Deduplication is performed using normalized content.

        Keeping the first occurrence preserves the highest
        ranked candidate because Retriever results are expected
        to already be similarity ordered.
        """

        seen: set[str] = set()

        unique_results = []

        for result in results:

            content = self._clean_content(
                result.content
            )

            if not content:
                continue

            content_key = self._normalize_text(
                content
            )

            if content_key in seen:
                continue

            seen.add(content_key)

            unique_results.append(
                result
            )

        return unique_results

    # ==========================================================
    # SAFE CONTENT
    # ==========================================================

    @staticmethod
    def _clean_content(
        content: Any,
    ) -> str:
        """
        Safely convert candidate content to text.

        Protects the reranker from malformed metadata or
        unexpected values.
        """

        if content is None:
            return ""

        if not isinstance(content, str):
            content = str(content)

        return content.strip()

    # ==========================================================
    # SAFE METADATA
    # ==========================================================

    @staticmethod
    def _safe_metadata(
        metadata: Any,
    ) -> dict[str, Any]:
        """
        Ensure metadata always has a dictionary structure.
        """

        if isinstance(
            metadata,
            dict,
        ):
            return dict(metadata)

        return {}

    # ==========================================================
    # SAFE SCORE
    # ==========================================================

    @staticmethod
    def _safe_score(
        score: Any,
    ) -> float:
        """
        Safely convert similarity scores to float.

        Invalid values become 0.0.
        """

        try:
            value = float(score)
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        if value != value:
            return 0.0

        return max(
            0.0,
            min(value, 1.0),
        )

    # ==========================================================
    # CLAMP
    # ==========================================================

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """
        Keep a numeric value inside a safe range.
        """

        return max(
            minimum,
            min(float(value), maximum),
        )


# ==============================================================
# SHARED RERANKER INSTANCE
# ==============================================================

reranker = Reranker(
    top_k=5,
    min_score=0.35,
    semantic_weight=0.75,
    lexical_weight=0.25,
    min_lexical_overlap=0.0,
)
