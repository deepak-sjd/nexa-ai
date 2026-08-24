# VectorStore

VectorStore is the persistent FAISS-based vector store used by NEXA AI.

It stores document embeddings and metadata and performs semantic similarity search.

## Responsibilities

- Store document embeddings.
- Store document chunk metadata.
- Persist the FAISS index to disk.
- Search for semantically similar chunks.
- Return relevant chunks with similarity scores.

## Technology

NEXA AI uses:

- FAISS for vector similarity search.
- NumPy for vector representation.
- JSON for metadata persistence.

The FAISS index uses `IndexFlatIP`.

Vectors are normalized before searching so inner product behaves like cosine similarity.

## Metadata

Each indexed chunk stores:

- vector_id
- document_id
- source
- chunk_index
- content

## Main Operations

### add_chunks()

Receives document chunks, creates embeddings through EmbeddingService, and adds them to FAISS.

### search()

Receives a query embedding and returns the most similar document chunks.

### count()

Returns the number of indexed chunks.

### clear()

Removes the current FAISS index and metadata.

## Relationship With EmbeddingService

EmbeddingService creates the vectors.

VectorStore stores and searches those vectors.

Flow:

Document
→ DocumentProcessor
→ EmbeddingService
→ VectorStore
→ FAISS

Query:

User Query
→ EmbeddingService
→ VectorStore
→ Similarity Search
→ Relevant Chunks