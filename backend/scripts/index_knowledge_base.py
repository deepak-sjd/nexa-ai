from pathlib import Path

from app.rag.document_processor import document_processor
from app.rag.vector_store import vector_store


# ============================================================
# CONFIGURATION
# ============================================================

KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")


# ============================================================
# INDEX KNOWLEDGE BASE
# ============================================================

def index_knowledge_base():

    print("=" * 70)
    print("NEXA AI KNOWLEDGE BASE INDEXING")
    print("=" * 70)

    if not KNOWLEDGE_BASE_DIR.exists():
        print(
            f"Knowledge base directory not found: "
            f"{KNOWLEDGE_BASE_DIR}"
        )
        return

    # Start clean so repeated indexing does not create duplicates.
    vector_store.clear()

    files = [
        path
        for path in KNOWLEDGE_BASE_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower()
        in document_processor.SUPPORTED_EXTENSIONS
    ]

    if not files:
        print("No supported documents found.")
        return

    print(f"\nFound {len(files)} documents.\n")

    total_chunks = 0

    for file_path in files:

        print(f"Processing: {file_path}")

        try:
            chunks = document_processor.process(
                str(file_path)
            )

            print(
                f"  → Created {len(chunks)} chunks"
            )

            if chunks:
                vector_store.add_chunks(
                    chunks=chunks,
                    source=str(file_path),
                    document_id=file_path.stem,
                )

                total_chunks += len(chunks)

        except Exception as e:

            print(
                f"  ✗ Failed: {e}"
            )

    print("\n" + "-" * 70)

    print(
        f"Total chunks created: {total_chunks}"
    )

    print(
        f"Total chunks indexed: {vector_store.count()}"
    )

    print("-" * 70)

    print(
        "\nKnowledge base indexing completed."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    index_knowledge_base()