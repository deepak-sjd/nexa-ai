from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageResponse
from app.services.ai_service import ai_service


router = APIRouter(
    prefix="/conversations",
    tags=["Messages"],
)


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    # Check conversation exists
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # Get all messages in chronological order
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    return messages


@router.post(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def create_message(
    conversation_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
):
    # 1. Check conversation exists
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # 2. Load previous conversation history
    previous_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    conversation_history = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in previous_messages
    ]

    # 3. Save user's message
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=data.content,
    )

    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    try:
        # 4. Send current message + previous history to Gemini
        ai_response = ai_service.generate_response(
            user_message=data.content,
            conversation_history=conversation_history,
        )

    except Exception as e:
        # Don't crash the API if Gemini fails
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(e)}",
        )

    # 5. Save assistant response
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=ai_response,
    )

    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    # 6. Return both messages
    return [
        user_message,
        assistant_message,
    ]