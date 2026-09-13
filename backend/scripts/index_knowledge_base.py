import hashlib
from pathlib import Path

from app.rag.document_processor import document_processor
from app.rag.vector_store import vector_store


# ============================================================
# CONFIGURATION
# ============================================================

KNOWLEDGE_BASE_DIR = Path("data/knowledge_base")

# Document IDs with this prefix belong to the SEPARATE
# user-upload subsystem (see app/api/routes/documents.py).
# This script must NEVER remove or rebuild those entries —
# it only owns document_ids that come from its own file scan
# below. Mixing the two caused a real bug: reindexing silently
# wiped every uploaded document's vectors while the Postgres
# `documents` table kept claiming they were still "completed".
UPLOADED_DOCUMENT_PREFIX = "upload_"


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

    if (
        file_path.suffix.lower()
        not in document_processor.SUPPORTED_EXTENSIONS
    ):
        return False

    if file_path.name in IGNORED_FILES:
        return False

    for part in file_path.parts:
        if part in IGNORED_DIRECTORIES:
            return False

    return True


# ============================================================
# COLLECT DOCUMENTS
# ============================================================

def collect_documents() -> list[Path]:
    """
    Collect project documentation from data/knowledge_base.

    NOTE: This deliberately does NOT index app/ (the codebase
    source). Mixing your own implementation source code into
    the same retrieval pool as user-facing documents caused
    files like message.py to get spuriously cited as "sources"
    for everyday questions that had nothing to do with the
    codebase — a generic word (e.g. "message") in a query could
    semantically collide with a class/file of the same name.
    """

    documents = []

    if KNOWLEDGE_BASE_DIR.exists():
        for path in KNOWLEDGE_BASE_DIR.rglob("*"):
            if should_index(path):
                documents.append(path)

    return sorted(
        set(documents),
        key=lambda path: str(path).lower(),
    )


# ============================================================
# STABLE DOCUMENT ID
# ============================================================

def make_document_id(file_path: Path) -> str:
    return (
        file_path
        .as_posix()
        .replace("/", "_")
        .replace("\\", "_")
    )


# ============================================================
# CONTENT HASH
# ============================================================

def file_hash(file_path: Path) -> str:
    """
    SHA-256 hash of a file's raw bytes.

    Used to detect whether a document has changed since the
    last indexing run, so unchanged documents are never
    re-embedded.
    """

    return hashlib.sha256(
        file_path.read_bytes()
    ).hexdigest()


# ============================================================
# INDEX KNOWLEDGE BASE (INCREMENTAL)
# ============================================================

def index_knowledge_base():

    print("=" * 70)
    print("NEXA AI KNOWLEDGE BASE INDEXING (incremental)")
    print("=" * 70)

    documents = collect_documents()

    if not documents:
        print("\nNo supported documents found.")
        return

    print(f"\nFound {len(documents)} documents on disk.\n")

    # --------------------------------------------------------
    # Split existing vector store metadata into two groups:
    #
    # 1. Uploaded documents (document_id starts with
    #    "upload_") — NOT owned by this script. Always carried
    #    forward untouched, no matter what this run finds.
    #
    # 2. Knowledge-base documents — owned by this script.
    #    Grouped by document_id so we know what's already
    #    indexed and whether its content has changed.
    # --------------------------------------------------------

    preserved_upload_entries: list[tuple[list[float], dict]] = []
    existing_by_doc: dict[str, dict] = {}

    for entry in vector_store.metadata:

        doc_id = entry.get("document_id")

        if doc_id is None:
            continue

        if doc_id.startswith(UPLOADED_DOCUMENT_PREFIX):
            vector = vector_store.get_vector(
                entry["vector_id"]
            )
            preserved_upload_entries.append(
                (vector, entry.copy())
            )
            continue

        bucket = existing_by_doc.setdefault(
            doc_id,
            {"hash": entry.get("document_hash"), "vector_ids": []},
        )

        bucket["vector_ids"].append(entry["vector_id"])

    print(
        f"Preserving {len(preserved_upload_entries)} chunks "
        f"from uploaded documents (untouched by this script).\n"
    )

    current_doc_ids: set[str] = set()

    # (vector, metadata) pairs reused from disk — NO API calls.
    reused_entries: list[tuple[list[float], dict]] = []

    # Files that are new or whose content changed.
    to_embed: list[tuple[Path, str, str]] = []

    skipped = 0
    hash_failures = 0

    for file_path in documents:

        document_id = make_document_id(file_path)
        current_doc_ids.add(document_id)

        try:
            current_hash = file_hash(file_path)
        except Exception as e:
            hash_failures += 1
            print(f"  ✗ Could not hash {file_path}: {e}")
            continue

        existing = existing_by_doc.get(document_id)

        if existing and existing["hash"] == current_hash:

            # Unchanged — reuse stored vectors, skip the API entirely.
            for vector_id in existing["vector_ids"]:

                vector = vector_store.get_vector(vector_id)
                metadata = vector_store.metadata[vector_id].copy()

                reused_entries.append((vector, metadata))

            skipped += 1
            continue

        to_embed.append((file_path, document_id, current_hash))

    removed_doc_ids = set(existing_by_doc.keys()) - current_doc_ids

    print(f"Unchanged documents (reused, no API calls): {skipped}")
    print(f"New / changed documents to embed:           {len(to_embed)}")
    print(f"Removed documents (no longer on disk):       {len(removed_doc_ids)}")
    print()

    # --------------------------------------------------------
    # Only new/changed documents hit the embedding API.
    # --------------------------------------------------------

    newly_embedded: list[tuple[list[float], dict]] = []
    embedded_files = 0
    failed_files = 0

    for file_path, document_id, current_hash in to_embed:

        print(f"Processing: {file_path}")

        try:
            chunks = document_processor.process(str(file_path))
        except Exception as e:
            failed_files += 1
            print(f"  ✗ Failed to process: {e}")
            continue

        if not chunks:
            print("  → 0 chunks, skipping")
            continue

        print(f"  → {len(chunks)} chunks, calling embedding API...")

        try:
            vectors = vector_store.embed_and_normalize(chunks)
        except Exception as e:
            failed_files += 1
            print(f"  ✗ Embedding failed: {e}")
            continue

        if not vectors:
            failed_files += 1
            print("  ✗ No embeddings returned")
            continue

        for offset, (vector, chunk) in enumerate(zip(vectors, chunks)):

            newly_embedded.append(
                (
                    vector,
                    {
                        "document_id": document_id,
                        "document_hash": current_hash,
                        "source": str(file_path),
                        "chunk_index": offset,
                        "content": chunk,
                    },
                )
            )

        embedded_files += 1

    # --------------------------------------------------------
    # Rebuild the index from preserved uploads + reused +
    # newly embedded knowledge-base vectors. This is the key
    # fix: uploaded documents are ALWAYS included, regardless
    # of this script's own file scan.
    # --------------------------------------------------------

    all_entries = (
        preserved_upload_entries
        + reused_entries
        + newly_embedded
    )

    vector_store.rebuild(all_entries)

    # ========================================================
    # FINAL REPORT
    # ========================================================

    print("\n" + "-" * 70)
    print(f"Uploaded document chunks preserved: {len(preserved_upload_entries)}")
    print(f"Documents unchanged (reused):        {skipped}")
    print(f"Documents embedded this run:         {embedded_files}")
    print(f"Documents failed:                    {failed_files + hash_failures}")
    print(f"Documents removed:                   {len(removed_doc_ids)}")
    print(f"Total chunks indexed:                {vector_store.count()}")
    print("-" * 70)

    print("\nKnowledge base indexing completed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    index_knowledge_base()