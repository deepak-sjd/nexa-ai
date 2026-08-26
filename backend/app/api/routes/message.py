from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import json

from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageResponse
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service


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

    rag_result = rag_service.search(
        query=data.content,
        retrieval_top_k=8,
        rerank_top_k=5,
    )

    retrieved_context = rag_result["context"]

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
       ai_response = llm_service.generate_response(
          user_message=data.content,
          conversation_history=conversation_history,
          retrieved_context= retrieved_context,
    )

    except Exception as e:
        print(f"AI service error: {e}")

        raise HTTPException(
           status_code=503,
           detail="AI service is temporarily unavailable. Please try again.",
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
    return [assistant_message]

@router.post(
    "/{conversation_id}/messages/stream",
)
def create_message_stream(
    conversation_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
):
    # ========================================================
    # 1. CHECK CONVERSATION
    # ========================================================

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

    # ========================================================
    # 2. LOAD RECENT HISTORY
    # ========================================================

    previous_messages = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id
        )
        .order_by(Message.created_at.desc())
        .limit(12)
        .all()
    )

    previous_messages.reverse()

    conversation_history = [
    {
        "role": message.role,
        "content": message.content,
    }
    for message in previous_messages
]


    # ========================================================
    # 3. RAG RETRIEVAL
    # ========================================================
    rag_result = rag_service.search(
       query=data.content,
       retrieval_top_k=8,
       rerank_top_k=5,
)
    retrieved_context = rag_result["context"]
    # ========================================================
    # 4. SAVE USER MESSAGE
    # ========================================================

    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=data.content,
    )

    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # ========================================================
    # 5. STREAM GEMINI RESPONSE
    # ========================================================

    def generate():

        full_response = ""

        try:

            for chunk in llm_service.generate_response_stream(
                user_message=data.content,
                conversation_history=conversation_history,
                retrieved_context=retrieved_context,
            ):

                full_response += chunk

                yield (
                    f"data: "
                    f"{json.dumps({'type': 'chunk', 'content': chunk})}"
                    "\n\n"
                )

            # =================================================
            # 6. SAVE COMPLETE AI RESPONSE
            # =================================================

            assistant_message = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
            )

            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

            # =================================================
            # 6. SEND COMPLETION EVENT
            # =================================================

            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "done",
                        "message": {
                            "id": assistant_message.id,
                            "conversation_id": conversation_id,
                            "role": "assistant",
                            "content": full_response,
                        },
                    }
                )
                + "\n\n"
            )

        except Exception as e:

            db.rollback()
            print("=" * 70)
            print("STREAMING ERROR")
            print(type(e).__name__)
            print(str(e))
            print("=" *70)

            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "message": str(e),
                    }
                )
                + "\n\n"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )