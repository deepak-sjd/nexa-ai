import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.document import Document
from app.models.user import User
from app.rag.document_processor import document_processor
from app.rag.vector_store import vector_store
from app.schemas.document import DocumentResponse


logger = get_logger(__name__)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".xlsx",
}


# ============================================================
# UPLOAD DOCUMENT
# ============================================================

@router.post(
    "/upload",
    response_model=DocumentResponse,
)
async def upload_document(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    original_name = file.filename or "upload"
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Allowed types: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    file_bytes = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File is too large. Maximum size is "
                f"{settings.max_upload_size_mb}MB."
            ),
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    # --------------------------------------------------------
    # Save to disk under a unique name (never trust the
    # original filename for the on-disk path).
    # --------------------------------------------------------

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    document_id = f"upload_{uuid.uuid4().hex[:16]}"
    stored_filename = f"{document_id}{extension}"
    stored_path = upload_dir / stored_filename

    stored_path.write_bytes(file_bytes)

    # --------------------------------------------------------
    # Create the tracking row up front (status=processing),
    # so a failure partway through still leaves a visible,
    # explainable record instead of vanishing silently.
    # --------------------------------------------------------

    document = Document(
        user_id=user_id,
        document_id=document_id,
        filename=original_name,
        stored_path=str(stored_path),
        file_type=extension.lstrip("."),
        file_size_bytes=len(file_bytes),
        status="processing",
        chunk_count=0,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # --------------------------------------------------------
    # Process: extract -> chunk -> embed -> index
    # --------------------------------------------------------

    try:
        chunks = document_processor.process(str(stored_path))

        if not chunks:
            document.status = "failed"
            document.error_message = (
                "No extractable text was found in this file."
            )
            db.commit()
            db.refresh(document)

            return document

        vector_store.add_chunks(
            chunks=chunks,
            source=original_name,
            document_id=document_id,
        )

        document.status = "completed"
        document.chunk_count = len(chunks)
        document.error_message = None

        db.commit()
        db.refresh(document)

        logger.info(
            "document_id=%s filename=%s chunks=%d "
            "status=completed",
            document_id,
            original_name,
            len(chunks),
        )

        return document

    except Exception as e:
        logger.exception(
            "document_id=%s filename=%s processing failed: %s",
            document_id,
            original_name,
            e,
        )

        document.status = "failed"
        document.error_message = str(e)

        db.commit()
        db.refresh(document)

        return document


# ============================================================
# LIST DOCUMENTS
# ============================================================

@router.get(
    "/user/{user_id}",
    response_model=list[DocumentResponse],
)
def list_documents(
    user_id: int,
    db: Session = Depends(get_db),
):
    documents = (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return documents


# ============================================================
# DELETE DOCUMENT
# ============================================================

@router.delete(
    "/{document_row_id}",
)
def delete_document(
    document_row_id: int,
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_row_id)
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    removed_chunks = vector_store.remove_document(
        document.document_id
    )

    stored_path = Path(document.stored_path)

    if stored_path.exists():
        stored_path.unlink()

    db.delete(document)
    db.commit()

    logger.info(
        "document_id=%s deleted, removed_chunks=%d",
        document.document_id,
        removed_chunks,
    )

    return {
        "message": "Document deleted successfully",
        "removed_chunks": removed_chunks,
    }