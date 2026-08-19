from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
)


router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    response_model=ConversationResponse,
)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
):
    conversation = Conversation(
        user_id=data.user_id,
        title=data.title,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation

@router.get(
    "/user/{user_id}",
    response_model=list[ConversationResponse],
)
def get_user_conversations(
    user_id: int,
    db: Session = Depends(get_db),
):
    # Check that the user exists
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

    # Get all conversations belonging to the user
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )

    return conversations