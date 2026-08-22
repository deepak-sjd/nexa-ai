from dataclasses import dataclass
from typing import Any

from app.rag.reranker import RerankedResult


@dataclass
class BuiltContext:
    """
    Final context prepared for the LLM.
    """

    context: str
    sources: list[dict[str, Any]]
    chunk_count: int


class ContextBuilder:
    """
    Builds safe, structured context from reranked RAG results.

    Responsibilities:
        1. Select the strongest chunks.
        2. Remove duplicate content.
        3. Add source information.
        4. Keep context within a configurable size.
        5. Clearly separate retrieved knowledge from instructions.
    """

    def __init__(
        self,
        max_chunks: int = 5,
        max_context_characters: int = 12000,
    ):
        self.max_chunks = max(
            1,
            max_chunks,
        )

        self.max_context_characters = max(
            1000,
            max_context_characters,
        )

    # ============================================================
    # REMOVE DUPLICATES
    # ============================================================

    def _remove_duplicates(
        self,
        results: list[RerankedResult],
    ) -> list[RerankedResult]:

        seen = set()
        unique_results = []

        for result in results:

            content_key = result.content.strip()

            if not content_key:
                continue

            if content_key in seen:
                continue

            seen.add(content_key)
            unique_results.append(result)

        return unique_results

    # ============================================================
    # BUILD SOURCE INFORMATION
    # ============================================================

    def _build_source(
        self,
        result: RerankedResult,
        index: int,
    ) -> dict[str, Any]:

        metadata = result.metadata or {}

        return {
            "index": index,
            "source": metadata.get(
                "source",
                "Unknown",
            ),
            "document_id": metadata.get(
                "document_id"
            ),
            "chunk_index": metadata.get(
                "chunk_index"
            ),
            "score": result.score,
        }

    # ============================================================
    # BUILD CONTEXT
    # ============================================================

    def build(
        self,
        results: list[RerankedResult],
    ) -> BuiltContext:
        """
        Convert reranked chunks into structured LLM context.
        """

        if not results:
            return BuiltContext(
                context="",
                sources=[],
                chunk_count=0,
            )

        unique_results = self._remove_duplicates(
            results
        )

        selected_results = unique_results[
            : self.max_chunks
        ]

        context_parts = []
        sources = []

        current_length = 0

        for index, result in enumerate(
            selected_results,
            start=1,
        ):

            content = result.content.strip()

            source = self._build_source(
                result,
                index,
            )

            source_name = source["source"]

            chunk_text = (
                f"[SOURCE {index}]\n"
                f"File: {source_name}\n"
                f"Relevance: {result.score:.4f}\n"
                f"Content:\n"
                f"{content}\n"
                f"[/SOURCE {index}]"
            )

            # ----------------------------------------------------
            # Context size protection
            # ----------------------------------------------------

            additional_length = len(
                chunk_text
            )

            if (
                current_length
                + additional_length
                > self.max_context_characters
            ):
                break

            context_parts.append(
                chunk_text
            )

            sources.append(source)

            current_length += (
                additional_length
            )

        final_context = "\n\n".join(
            context_parts
        )

        return BuiltContext(
            context=final_context,
            sources=sources,
            chunk_count=len(sources),
        )


# ============================================================
# SHARED CONTEXT BUILDER
# ============================================================

context_builder = ContextBuilder(
    max_chunks=5,
    max_context_characters=12000,
)