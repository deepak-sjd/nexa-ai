
from pathlib import Path

from app.rag.document_processor import document_processor
from app.rag.vector_store import vector_store


# ============================================================
# CONFIGURATION
# ============================================================

KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")
APP_DIR = Path("app")


# ============================================================
# DIRECTORIES / FILES TO IGNORE
# ============================================================

IGNORED_DIRECTORIES = {
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
}

IGNORED_FILES = {
    ".env",
}


# ============================================================
# CHECK WHETHER FILE SHOULD BE INDEXED
# ============================================================

def should_index(file_path: Path) -> bool:
    """
    Decide whether a file should become part of
    the NEXA AI knowledge base.
    """

    if not file_path.is_file():
        return False

    # Ignore unsupported extensions
    if (
        file_path.suffix.lower()
        not in document_processor.SUPPORTED_EXTENSIONS
    ):
        return False

    # Ignore sensitive / unwanted files
    if file_path.name in IGNORED_FILES:
        return False

    # Ignore unwanted directories
    for part in file_path.parts:
        if part in IGNORED_DIRECTORIES:
            return False

    return True


# ============================================================
# COLLECT DOCUMENTS
# ============================================================

def collect_documents() -> list[Path]:
    """
    Collect both:

    1. Project documentation from data/knowledge_base
    2. Actual NEXA AI source code from app/
    """

    documents = []

    # --------------------------------------------------------
    # 1. Knowledge-base documentation
    # --------------------------------------------------------

    if KNOWLEDGE_BASE_DIR.exists():

        for path in KNOWLEDGE_BASE_DIR.rglob("*"):

            if should_index(path):
                documents.append(path)

    # --------------------------------------------------------
    # 2. Actual application source code
    # --------------------------------------------------------

    if APP_DIR.exists():

        for path in APP_DIR.rglob("*"):

            if should_index(path):
                documents.append(path)

    # Remove duplicates and sort
    documents = sorted(
        set(documents),
        key=lambda path: str(path).lower(),
    )

    return documents


# ============================================================
# INDEX KNOWLEDGE BASE
# ============================================================

def index_knowledge_base():

    print("=" * 70)
    print("NEXA AI KNOWLEDGE BASE INDEXING")
    print("=" * 70)

    documents = collect_documents()

    if not documents:
        print("\nNo supported documents found.")
        return

    print(
        f"\nFound {len(documents)} documents to index.\n"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Start clean on every indexing run.
    #
    # This prevents duplicate vectors when we run
    # the indexing script multiple times.
    # --------------------------------------------------------

    vector_store.clear()

    total_chunks = 0
    successful_files = 0
    failed_files = 0

    # --------------------------------------------------------
    # PROCESS EVERY DOCUMENT
    # --------------------------------------------------------

    for file_path in documents:

        print(f"Processing: {file_path}")

        try:

            chunks = document_processor.process(
                str(file_path)
            )

            print(
                f"  → Created {len(chunks)} chunks"
            )

            if chunks:

                # Create a stable document ID
                document_id = str(
                    file_path
                    .as_posix()
                    .replace("/", "_")
                    .replace("\\", "_")
                )

                vector_store.add_chunks(
                    chunks=chunks,
                    source=str(file_path),
                    document_id=document_id,
                )

                total_chunks += len(chunks)

            successful_files += 1

        except Exception as e:

            failed_files += 1

            print(
                f"  ✗ Failed: {e}"
            )

    # ========================================================
    # FINAL REPORT
    # ========================================================

    print("\n" + "-" * 70)

    print(
        f"Documents processed: {successful_files}"
    )

    print(
        f"Documents failed:    {failed_files}"
    )

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
