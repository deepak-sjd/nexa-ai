# RAGService

RAGService is the main orchestration service for the NEXA AI retrieval pipeline.

It connects the Retriever, Reranker, and Context Builder.

RAGService does not call the LLM.

## Pipeline

User Query
→ Retriever
→ Reranker
→ Context Builder
→ Final RAG Context
→ LLM

## Responsibilities

- Retrieve relevant knowledge.
- Rerank retrieved knowledge.
- Build LLM-ready context.
- Provide a single interface for the complete RAG pipeline.

## Retrieve

The `retrieve()` method calls the Retriever.

The default retrieval size is 8 results.

## Rerank

The `rerank()` method sends retrieved results to the Reranker.

The default final reranking size is 5 results.

## Build Context

The `build_context()` method sends reranked results to the Context Builder.

The Context Builder converts the selected results into text that can be provided to the LLM.

## Search

The `search()` method executes the complete pipeline:

1. Receive the user query.
2. Retrieve semantic candidates.
3. Rerank the candidates.
4. Build the final context.
5. Return the query, retrieved results, reranked results, and final context.

## Important Design

RAGService separates knowledge retrieval from language generation.

The RAG system finds the relevant project knowledge.

The LLM uses that knowledge to generate the final answer.

## Complete Relationship

DocumentProcessor
→ EmbeddingService
→ VectorStore
→ Retriever
→ Reranker
→ Context Builder
→ RAGService
→ LLM