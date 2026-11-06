import functools
import threading
from typing import Any

import faiss
import numpy as np

from app.core.database import SessionLocal
from app.models.vector_chunk import VectorChunk
from app.rag.embeddings import embedding_service


def _locked(method):
    """FAISS is not thread-safe and FastAPI runs routes in a thread
    pool, so every read/write of the in-memory index takes this lock."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class VectorStore:
    """
    FAISS vector store that persists to the database.

    - Search runs on an in-memory FAISS index (fast).
    - Every chunk and its embedding is also saved in the
      `vector_chunks` table, and the index is rebuilt from that table
      on start-up - so nothing is lost when the server restarts or the
      host wipes its disk.

    Run the API with a single worker process: each worker would keep
    its own in-memory copy of the index.
    """

    def __init__(self):
        self._lock = threading.RLock()

        self.index = None
        self.metadata: list[dict[str, Any]] = []

        self._load()

    # ============================================================
    # LOAD FROM DATABASE
    # ============================================================

    def _load(self):
        """
        Rebuild the in-memory index from the vector_chunks table.
        """

        self.index = None
        self.metadata = []

        with SessionLocal() as session:
            rows = (
                session.query(VectorChunk)
                .order_by(VectorChunk.id)
                .all()
            )

        if not rows:
            return

        vectors = np.vstack(
            [
                np.frombuffer(row.embedding, dtype="float32")
                for row in rows
            ]
        )

        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

        self.metadata = [
            {
                "vector_id": position,
                "document_id": row.document_id,
                "source": row.source,
                "chunk_index": row.chunk_index,
                "content": row.content,
            }
            for position, row in enumerate(rows)
        ]

    # ============================================================
    # DATABASE WRITES
    # ============================================================

    @staticmethod
    def _to_rows(
        vectors: np.ndarray,
        metadata: list[dict[str, Any]],
    ) -> list[VectorChunk]:
        return [
            VectorChunk(
                document_id=entry.get("document_id"),
                source=entry.get("source", ""),
                chunk_index=entry.get("chunk_index", 0),
                content=entry.get("content", ""),
                embedding=np.asarray(
                    vectors[position],
                    dtype="float32",
                ).tobytes(),
            )
            for position, entry in enumerate(metadata)
        ]

    def _replace_all_rows(self):
        """
        Make the table match the in-memory index exactly.
        """

        with SessionLocal() as session:
            session.query(VectorChunk).delete()

            if self.index is not None and self.index.ntotal > 0:
                vectors = self.index.reconstruct_n(
                    0,
                    self.index.ntotal,
                )

                session.add_all(
                    self._to_rows(vectors, self.metadata)
                )

            session.commit()

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
        Convert chunks into embeddings, save them to the database and
        add them to the FAISS index.
        """

        if not chunks:
            return

        # The slow part (embedding API) runs WITHOUT the lock, so other
        # users can keep searching while a document is indexed.
        embeddings = embedding_service.embed_documents(
            chunks
        )

        vectors = np.asarray(
            embeddings,
            dtype="float32",
        )

        # Normalize so inner product behaves like cosine similarity.
        faiss.normalize_L2(vectors)

        self._append(vectors, chunks, source, document_id)

    @_locked
    def _append(
        self,
        vectors: np.ndarray,
        chunks: list[str],
        source: str,
        document_id: str | None,
    ):
        start_id = len(self.metadata)

        new_metadata = [
            {
                "vector_id": start_id + offset,
                "document_id": document_id,
                "source": source,
                "chunk_index": offset,
                "content": chunk,
            }
            for offset, chunk in enumerate(chunks)
        ]

        # Database first: if it fails, memory stays unchanged.
        with SessionLocal() as session:
            session.add_all(self._to_rows(vectors, new_metadata))
            session.commit()

        if self.index is None:
            self.index = faiss.IndexFlatIP(vectors.shape[1])

        self.index.add(vectors)
        self.metadata.extend(new_metadata)

    # ============================================================
    # GET STORED VECTOR (NO RECOMPUTATION)
    # ============================================================

    @_locked
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

    @_locked
    def rebuild(
        self,
        entries: list[tuple[list[float], dict[str, Any]]],
        persist: bool = True,
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
            if persist:
                self._replace_all_rows()
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

        if persist:
            self._replace_all_rows()

    # ============================================================
    # REMOVE ONE DOCUMENT'S CHUNKS
    # ============================================================

    @_locked
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

        with SessionLocal() as session:
            session.query(VectorChunk).filter(
                VectorChunk.document_id == document_id
            ).delete()
            session.commit()

        self.rebuild(kept_entries, persist=False)

        return removed_count

    # ============================================================
    # SEARCH
    # ============================================================

    @staticmethod
    def _is_visible(
        metadata: dict[str, Any],
        allowed_document_ids: set[str] | None,
    ) -> bool:
        """None = no filtering. Otherwise a chunk is only visible if its
        document belongs to the asking user."""
        if allowed_document_ids is None:
            return True

        return str(metadata.get("document_id", "")) in allowed_document_ids

    @_locked
    def search(
        self,
        embedding: list[float],
        top_k: int = 5,
        allowed_document_ids: set[str] | None = None,
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

        # When filtering by owner, look at every vector and keep the
        # first top_k visible ones, so other users' chunks can never
        # crowd the asking user's chunks out of the results.
        search_count = (
            self.index.ntotal
            if allowed_document_ids is not None
            else min(top_k, self.index.ntotal)
        )

        scores, indices = self.index.search(
            query_vector,
            search_count,
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

            if not self._is_visible(metadata, allowed_document_ids):
                continue

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

            if len(results) >= top_k:
                break

        return results

    # ============================================================
    # COUNT
    # ============================================================

    @_locked
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

    @_locked
    def clear(self):
        """
        Delete every chunk (memory and database).
        """

        self.index = None
        self.metadata = []

        with SessionLocal() as session:
            session.query(VectorChunk).delete()
            session.commit()


vector_store = VectorStore()