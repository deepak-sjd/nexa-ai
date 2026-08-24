# EmbeddingService

EmbeddingService converts text into numerical embedding vectors.

NEXA AI uses the Gemini `gemini-embedding-001` model for embeddings.

## Responsibilities

- Convert document chunks into embedding vectors.
- Convert user queries into embedding vectors.
- Provide embeddings to the VectorStore.
- Enable semantic similarity search.

## Main Methods

### embed_text()

Converts one text string into an embedding vector.

### embed_documents()

Converts multiple document chunks into embedding vectors.

### embed_query()

Converts the user's question into an embedding vector.

## RAG Relationship

The EmbeddingService is used by both document indexing and query retrieval.

Document flow:

Document
→ DocumentProcessor
→ Text Chunks
→ EmbeddingService
→ Embedding Vectors
→ VectorStore

Query flow:

User Query
→ EmbeddingService
→ Query Embedding
→ VectorStore Search
→ Relevant Chunks