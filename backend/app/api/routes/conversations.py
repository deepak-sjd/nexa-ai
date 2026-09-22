from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.image_storage import delete_image_files

from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
)


router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


# ============================================================
# CREATE CONVERSATION
# ============================================================

@router.post(
    "",
    response_model=ConversationResponse,
)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
):

    # Check that user exists
    user = (
        db.query(User)
        .filter(User.id == data.user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    conversation = Conversation(
        user_id=data.user_id,
        title=data.title,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


# ============================================================
# GET USER CONVERSATIONS
# ============================================================

@router.get(
    "/user/{user_id}",
    response_model=list[ConversationResponse],
)
def get_user_conversations(
    user_id: int,
    db: Session = Depends(get_db),
):

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    conversations = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == user_id
        )
        .order_by(
            Conversation.is_pinned.desc(),
            Conversation.created_at.desc(),
        )
        .all()
    )

    return conversations


# ============================================================
# GET SINGLE CONVERSATION
# ============================================================

@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id
        )
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return conversation


# ============================================================
# UPDATE CONVERSATION (rename and/or pin)
# ============================================================

@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def update_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    db: Session = Depends(get_db),
):

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id
        )
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    update_fields = data.model_dump(
        exclude_unset=True
    )

    if "title" in update_fields:
        conversation.title = update_fields["title"]

    if "is_pinned" in update_fields:
        conversation.is_pinned = update_fields["is_pinned"]

    db.commit()
    db.refresh(conversation)

    return conversation


# ============================================================
# DELETE CONVERSATION
# ============================================================

@router.delete(
    "/{conversation_id}",
)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id
        )
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # Remember which image files belong to this conversation. The
    # rows are removed by the FK cascade, but the files on disk are
    # not — without this, "deleted" images would stay reachable by URL.
    image_filenames = [
        row[0]
        for row in db.query(Message.image_filename)
        .filter(
            Message.conversation_id == conversation_id,
            Message.image_filename.isnot(None),
        )
        .all()
    ]

    db.delete(conversation)
    db.commit()

    # After the commit, so a failed delete never loses images.
    delete_image_files(image_filenames)

    return {
        "message": "Conversation deleted successfully",
        "conversation_id": conversation_id,
    }