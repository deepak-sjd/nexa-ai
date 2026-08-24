# Retriever

Retriever is the semantic retrieval component of the NEXA AI RAG pipeline.

Its job is to find the most relevant document chunks for a user's query.

## Responsibilities

- Convert the user query into an embedding.
- Search the VectorStore.
- Normalize retrieval results.
- Filter low-relevance results.
- Remove duplicate chunks.
- Sort results by similarity score.
- Return the final top-K results.

## Retrieval Process

User Query
→ Query Embedding
→ VectorStore Search
→ Candidate Results
→ Relevance Filtering
→ Duplicate Removal
→ Sorting
→ Top-K Results

## Query Embedding

Retriever uses EmbeddingService to convert the user's question into an embedding vector.

## Vector Search

Retriever sends the query embedding to VectorStore.

The VectorStore returns chunks containing:

- content
- similarity score
- metadata

## Relevance Filtering

Retriever uses a similarity threshold.

The default threshold is `0.35`.

Results below this threshold are removed.

## Candidate Retrieval

Retriever retrieves more candidates than the final requested number.

For example, when `top_k` is 8, it can retrieve up to 24 candidates before filtering and deduplication.

This gives the pipeline more candidates to work with.

## Final Result

The strongest remaining chunks are sorted by similarity score and returned to the RAG pipeline.