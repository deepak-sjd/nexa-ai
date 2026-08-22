from typing import Any

from app.rag.retriever import retriever
from app.rag.reranker import reranker
from app.rag.context_builder import context_builder


class RAGService:
    """
    Main RAG orchestration service.

    Pipeline:

        User Query
            ↓
        Retriever
            ↓
        Reranker
            ↓
        Context Builder
            ↓
        Final RAG Context

    This service does NOT call the LLM.
    It only finds and prepares relevant knowledge.
    """

    def __init__(
        self,
        retriever_service=None,
        reranker_service=None,
        context_builder_service=None,
    ):
        self.retriever = (
            retriever_service
            or retriever
        )

        self.reranker = (
            reranker_service
            or reranker
        )

        self.context_builder = (
            context_builder_service
            or context_builder
        )

    # ============================================================
    # RETRIEVE KNOWLEDGE
    # ============================================================

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
    ) -> list[Any]:
        """
        Retrieve relevant chunks from the vector store.
        """

        if not query or not query.strip():
            return []

        return self.retriever.retrieve(
            query=query.strip(),
            top_k=top_k,
        )

    # ============================================================
    # RERANK KNOWLEDGE
    # ============================================================

    def rerank(
        self,
        query: str,
        results: list[Any],
        top_k: int = 5,
    ) -> list[Any]:
        """
        Rerank retrieved chunks using the reranker.
        """

        if not results:
            return []

        return self.reranker.rerank(
            query=query,
            results=results,
            top_k=top_k,
        )

    # ============================================================
    # BUILD CONTEXT
    # ============================================================

    def build_context(
        self,
        results: list[Any],
    ) -> str:
        """
        Convert reranked results into
        LLM-ready context.
        """

        if not results:
            return ""

        return self.context_builder.build(
            results
        )

    # ============================================================
    # COMPLETE RAG PIPELINE
    # ============================================================

    def search(
        self,
        query: str,
        retrieval_top_k: int = 8,
        rerank_top_k: int = 5,
    ) -> dict[str, Any]:
        """
        Execute the complete RAG pipeline.

        Returns:

        {
            "query": "...",
            "retrieved": [...],
            "reranked": [...],
            "context": "..."
        }
        """

        query = query.strip()

        if not query:
            return {
                "query": "",
                "retrieved": [],
                "reranked": [],
                "context": "",
            }

        # --------------------------------------------------------
        # 1. Semantic retrieval
        # --------------------------------------------------------

        retrieved_results = self.retrieve(
            query=query,
            top_k=retrieval_top_k,
        )

        # --------------------------------------------------------
        # 2. Cross-encoder / relevance reranking
        # --------------------------------------------------------

        reranked_results = self.rerank(
            query=query,
            results=retrieved_results,
            top_k=rerank_top_k,
        )

        # --------------------------------------------------------
        # 3. Build final context
        # --------------------------------------------------------

        context = self.build_context(
            reranked_results
        )

        return {
            "query": query,
            "retrieved": retrieved_results,
            "reranked": reranked_results,
            "context": context,
        }

    # ============================================================
    # SIMPLE CONTEXT API
    # ============================================================

    def get_context(
        self,
        query: str,
        retrieval_top_k: int = 8,
        rerank_top_k: int = 5,
    ) -> str:
        """
        Convenience method.

        Returns only the final context that
        will eventually be sent to the LLM.
        """

        result = self.search(
            query=query,
            retrieval_top_k=retrieval_top_k,
            rerank_top_k=rerank_top_k,
        )

        return result["context"]


# ================================================================
# SHARED SERVICE INSTANCE
# ================================================================

rag_service = RAGService()