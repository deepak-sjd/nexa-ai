from pathlib import Path
import json
from typing import Any

import faiss
import numpy as np

from app.rag.embeddings import embedding_service


class VectorStore:
    """
    Persistent FAISS vector store.

    Responsibilities:
    - Store document embeddings
    - Store chunk metadata
    - Persist FAISS index to disk
    - Search for semantically similar chunks
    """

    def __init__(
        self,
        index_path: str = "data/vector_store/index.faiss",
        metadata_path: str = "data/vector_store/metadata.json",
    ):
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)

        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.index = None
        self.metadata: list[dict[str, Any]] = []

        self._load()

    # ============================================================
    # LOAD EXISTING STORE
    # ============================================================

    def _load(self):
        """
        Load existing FAISS index and metadata.
        """

        if (
            self.index_path.exists()
            and self.metadata_path.exists()
        ):
            self.index = faiss.read_index(
                str(self.index_path)
            )

            with open(
                self.metadata_path,
                "r",
                encoding="utf-8",
            ) as file:
                self.metadata = json.load(file)

            return

        self.index = None
        self.metadata = []

    # ============================================================
    # SAVE STORE
    # ============================================================

    def _save(self):
        """
        Persist FAISS index and metadata.
        """

        if self.index is not None:
            faiss.write_index(
                self.index,
                str(self.index_path),
            )

        with open(
            self.metadata_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self.metadata,
                file,
                ensure_ascii=False,
                indent=2,
            )

    # ============================================================
    # ADD DOCUMENT CHUNKS
    # ============================================================

    def add_chunks(
        self,
        chunks: list[str],
        source: str,
        document_id: str | None = None,
    ):
        """
        Convert chunks into embeddings and add them
        to the FAISS index.
        """

        if not chunks:
            return

        embeddings = embedding_service.embed_documents(
            chunks
        )

        vectors = np.asarray(
            embeddings,
            dtype="float32",
        )

        # --------------------------------------------------------
        # Create index on first insertion
        # --------------------------------------------------------

        if self.index is None:

            dimension = vectors.shape[1]

            self.index = faiss.IndexFlatIP(
                dimension
            )

            # Normalize vectors so inner product
            # behaves like cosine similarity.
            faiss.normalize_L2(vectors)

            self.index.add(vectors)

        else:

            # Normalize before adding
            faiss.normalize_L2(vectors)

            self.index.add(vectors)

        # --------------------------------------------------------
        # Store metadata
        # --------------------------------------------------------

        start_id = len(self.metadata)

        for offset, chunk in enumerate(chunks):

            self.metadata.append(
                {
                    "vector_id": start_id + offset,
                    "document_id": document_id,
                    "source": source,
                    "chunk_index": offset,
                    "content": chunk,
                }
            )

        self._save()

    # ============================================================
    # GET STORED VECTOR (NO RECOMPUTATION)
    # ============================================================

    def get_vector(self, vector_id: int) -> list[float]:
        """
        Return the already-stored (normalized) vector for a given
        vector_id, read directly from FAISS.

        Used by incremental indexing to reuse embeddings for
        unchanged documents without calling the embedding API again.
        """

        if self.index is None:
            raise RuntimeError(
                "Vector store is empty; no vectors to reconstruct."
            )

        return self.index.reconstruct(int(vector_id)).tolist()

    # ============================================================
    # EMBED WITHOUT INDEXING
    # ============================================================

    def embed_and_normalize(
        self,
        chunks: list[str],
    ) -> list[list[float]]:
        """
        Embed chunks via the embedding API and L2-normalize them,
        WITHOUT adding them to the index yet.

        This lets callers (e.g. incremental indexing) collect
        vectors for multiple documents and add them all at once
        via `rebuild()`.
        """

        if not chunks:
            return []

        embeddings = embedding_service.embed_documents(chunks)

        if not embeddings:
            return []

        vectors = np.asarray(
            embeddings,
            dtype="float32",
        )

        faiss.normalize_L2(vectors)

        return vectors.tolist()

    # ============================================================
    # REBUILD FROM (VECTOR, METADATA) PAIRS
    # ============================================================

    def rebuild(
        self,
        entries: list[tuple[list[float], dict[str, Any]]],
    ):
        """
        Rebuild the entire index from a list of
        (vector, metadata) pairs.

        Vectors are assumed to already be L2-normalized (either
        reused from `get_vector()` or produced by
        `embed_and_normalize()`), so this performs NO embedding
        API calls itself.
        """

        self.index = None
        self.metadata = []

        if not entries:
            self._save()
            return

        vectors = np.asarray(
            [vector for vector, _ in entries],
            dtype="float32",
        )

        dimension = vectors.shape[1]

        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(vectors)

        for vector_id, (_, metadata) in enumerate(entries):

            entry = dict(metadata)
            entry["vector_id"] = vector_id

            self.metadata.append(entry)

        self._save()

    # ============================================================
    # REMOVE ONE DOCUMENT'S CHUNKS
    # ============================================================

    def remove_document(self, document_id: str) -> int:
        """
        Remove all chunks belonging to a given document_id and
        rebuild the index from the remaining vectors.

        Returns the number of chunks removed. No embedding API
        calls are made — remaining vectors are reused as-is.
        """

        if self.index is None:
            return 0

        kept_entries: list[tuple[list[float], dict[str, Any]]] = []
        removed_count = 0

        for entry in self.metadata:

            if entry.get("document_id") == document_id:
                removed_count += 1
                continue

            vector = self.get_vector(entry["vector_id"])
            kept_entries.append((vector, entry))

        if removed_count == 0:
            return 0

        self.rebuild(kept_entries)

        return removed_count

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search FAISS using a pre-compute query embedding.
        """

        if self.index is None:
            return []

        if self.index.ntotal == 0:
            return []

        if not embedding:
            return []

        query_vector = np.asarray(
            [embedding],
            dtype="float32",
        )

   # Normalize for cosine similarity
        faiss.normalize_L2(query_vector)

        scores, indices = self.index.search(
            query_vector,
            min(top_k, self.index.ntotal),
        )

        results = []

        for score, index_id in zip(
            scores[0],
            indices[0],
        ):

            if index_id < 0:
                continue

            if index_id >= len(self.metadata):
                continue

            metadata = self.metadata[index_id].copy()

            results.append(
                {
                    "content": metadata.get(
                        "content",
                        "",
                    ),
                    "score": float(score),
                    "metadata": metadata,
                }
            )

        return results

    # ============================================================
    # COUNT
    # ============================================================

    def count(self) -> int:
        """
        Return number of indexed chunks.
        """

        if self.index is None:
            return 0

        return self.index.ntotal

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self):
        """
        Delete the current vector index and metadata.
        """

        self.index = None
        self.metadata = []

        if self.index_path.exists():
            self.index_path.unlink()

        if self.metadata_path.exists():
            self.metadata_path.unlink()


# ================================================================
# SHARED INSTANCE
# ================================================================

vector_store = VectorStore()