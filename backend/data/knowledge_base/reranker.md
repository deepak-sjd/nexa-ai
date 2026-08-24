# Reranker

Reranker is the second-stage relevance component in the NEXA AI RAG pipeline.

It receives candidate chunks from the Retriever and selects the strongest results.

## Responsibilities

- Receive retrieved chunks.
- Remove weak candidates.
- Calculate a reranking score.
- Sort results by relevance.
- Return the top results.

## Current Implementation

The current Reranker uses the original semantic retrieval score as its reranking score.

It does not yet use a separate cross-encoder model.

This design keeps the Reranker interface separate so a real cross-encoder or reranking model can be added later.

## Relevance Filtering

The default minimum score is `0.35`.

Results below this score are ignored.

## Output

Each reranked result contains:

- content
- score
- original_score
- metadata

## RAG Relationship

Retriever finds candidate knowledge.

Reranker selects the strongest candidates.

Flow:

User Query
→ Retriever
→ Candidate Chunks
→ Reranker
→ Best Chunks
→ Context Builder