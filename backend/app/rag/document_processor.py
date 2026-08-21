from pathlib import Path
from typing import List


class DocumentProcessor:
    """
    Loads documents and splits their text into smaller chunks.

    These chunks will later be converted into embeddings
    and stored in the vector database.
    """

    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".md",
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".csv",
    }

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size"
            )

    # ============================================================
    # LOAD DOCUMENT
    # ============================================================

    def load_document(self, file_path: str) -> str:
        """
        Read a supported text-based document.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {file_path}"
            )

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported document type: {path.suffix}"
            )

        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    # ============================================================
    # CLEAN TEXT
    # ============================================================

    def clean_text(self, text: str) -> str:
        """
        Basic text cleanup.
        """

        lines = [
            line.strip()
            for line in text.splitlines()
        ]

        cleaned_lines = [
            line
            for line in lines
            if line
        ]

        return "\n".join(cleaned_lines)

    # ============================================================
    # SPLIT TEXT
    # ============================================================

    def split_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Example:

        chunk 1: 0    -> 1000
        chunk 2: 850  -> 1850
        chunk 3: 1700 -> 2700

        The overlap helps preserve context between chunks.
        """

        text = text.strip()

        if not text:
            return []

        chunks = []

        start = 0
        text_length = len(text)

        while start < text_length:

            end = min(
                start + self.chunk_size,
                text_length,
            )

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = end - self.chunk_overlap

        return chunks

    # ============================================================
    # PROCESS DOCUMENT
    # ============================================================

    def process(self, file_path: str) -> List[str]:
        """
        Complete document-processing pipeline.
        """

        raw_text = self.load_document(file_path)

        cleaned_text = self.clean_text(
            raw_text
        )

        chunks = self.split_text(
            cleaned_text
        )

        return chunks


# Shared service instance
document_processor = DocumentProcessor()