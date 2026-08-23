from app.rag.document_processor import document_processor
from app.rag.vector_store import vector_store


file_path = "data/test_document.txt"

chunks = document_processor.process(file_path)

print(f"Created {len(chunks)} chunks.")

vector_store.add_chunks(
    chunks=chunks,
    source=file_path,
    document_id="test-document-001",
)

print(
    f"Successfully indexed {vector_store.count()} chunks."
)