from sqlalchemy import Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VectorChunk(Base):
    """
    One searchable chunk of an uploaded document, with its embedding.

    The search index (FAISS) lives in memory and is rebuilt from this
    table on start-up, so documents survive restarts and redeploys on
    hosts that wipe the disk.
    """

    __tablename__ = "vector_chunks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # Matches documents.document_id (the "upload_..." key).
    document_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # L2-normalized float32 vector, stored as raw bytes.
    embedding: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )