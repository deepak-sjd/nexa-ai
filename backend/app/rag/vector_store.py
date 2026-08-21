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
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search the vector store using semantic similarity.
        """

        if self.index is None:
            return []

        if self.index.ntotal == 0:
            return []

        query_embedding = (
            embedding_service.embed_query(query)
        )

        query_vector = np.asarray(
            [query_embedding],
            dtype="float32",
        )

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

            metadata["score"] = float(score)

            results.append(metadata)

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
