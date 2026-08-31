import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
import json

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageResponse
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service


logger = get_logger(__name__)


router = APIRouter(
    prefix="/conversations",
    tags=["Messages"],
)


DEFAULT_CONVERSATION_TITLE = "New Conversation"


def generate_conversation_title(
    text: str,
    max_length: int = 48,
) -> str:
    """
    Derive a short, human-readable conversation title from the
    first user message. No LLM call — pure string truncation,
    so it costs nothing and never fails.
    """

    cleaned = " ".join(text.strip().split())

    if not cleaned:
        return DEFAULT_CONVERSATION_TITLE

    if len(cleaned) <= max_length:
        return cleaned

    truncated = cleaned[:max_length].rsplit(" ", 1)[0]

    return f"{truncated}..."


def maybe_autotitle_conversation(
    conversation: Conversation,
    is_first_message: bool,
    first_message_content: str,
    db: Session,
) -> bool:
    """
    If this is the conversation's first message and it still has
    the default placeholder title, rename it based on the
    message content. Returns True if the title changed.
    """

    if not is_first_message:
        return False

    if conversation.title != DEFAULT_CONVERSATION_TITLE:
        # User already renamed it manually — never override that.
        return False

    conversation.title = generate_conversation_title(
        first_message_content
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return True


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

    retrieval_started_at = time.perf_counter()

    rag_result = rag_service.search(
        query=data.content,
        retrieval_top_k=8,
        rerank_top_k=5,
    )

    retrieved_context = rag_result["context"]

    retrieval_seconds = (
        time.perf_counter() - retrieval_started_at
    )

    logger.info(
        "conversation=%s retrieval_seconds=%.3f "
        "retrieved_chunks=%d reranked_chunks=%d "
        "context_chars=%d",
        conversation_id,
        retrieval_seconds,
        len(rag_result.get("retrieved", [])),
        len(rag_result.get("reranked", [])),
        len(retrieved_context or ""),
    )

    is_first_message = len(previous_messages) == 0

    # 3. Save user's message
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=data.content,
    )

    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    maybe_autotitle_conversation(
        conversation=conversation,
        is_first_message=is_first_message,
        first_message_content=data.content,
        db=db,
    )

    generation_started_at = time.perf_counter()

    try:
        # 4. Send current message + previous history to Gemini
        ai_response = llm_service.generate_response(
            user_message=data.content,
            conversation_history=conversation_history,
            retrieved_context=retrieved_context,
        )

    except Exception as e:
        logger.exception(
            "conversation=%s AI service error: %s",
            conversation_id,
            e,
        )

        raise HTTPException(
            status_code=503,
            detail="AI service is temporarily unavailable. Please try again.",
        )

    generation_seconds = (
        time.perf_counter() - generation_started_at
    )

    logger.info(
        "conversation=%s total_generation_seconds=%.3f "
        "response_chars=%d",
        conversation_id,
        generation_seconds,
        len(ai_response or ""),
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
    retrieval_started_at = time.perf_counter()

    rag_result = rag_service.search(
        query=data.content,
        retrieval_top_k=8,
        rerank_top_k=5,
    )
    retrieved_context = rag_result["context"]

    retrieval_seconds = (
        time.perf_counter() - retrieval_started_at
    )

    logger.info(
        "conversation=%s retrieval_seconds=%.3f "
        "retrieved_chunks=%d reranked_chunks=%d "
        "context_chars=%d",
        conversation_id,
        retrieval_seconds,
        len(rag_result.get("retrieved", [])),
        len(rag_result.get("reranked", [])),
        len(retrieved_context or ""),
    )

    is_first_message = len(previous_messages) == 0

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

    title_changed = maybe_autotitle_conversation(
        conversation=conversation,
        is_first_message=is_first_message,
        first_message_content=data.content,
        db=db,
    )

    # ========================================================
    # 5. STREAM GEMINI RESPONSE
    # ========================================================

    def generate():

        full_response = ""

        generation_started_at = time.perf_counter()
        first_chunk_at = None
        chunk_count = 0

        try:

            for chunk in llm_service.generate_response_stream(
                user_message=data.content,
                conversation_history=conversation_history,
                retrieved_context=retrieved_context,
            ):

                if first_chunk_at is None:
                    first_chunk_at = time.perf_counter()

                chunk_count += 1
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

            generation_finished_at = time.perf_counter()

            time_to_first_chunk = (
                (first_chunk_at - generation_started_at)
                if first_chunk_at
                else None
            )

            total_generation_seconds = (
                generation_finished_at - generation_started_at
            )

            logger.info(
                "conversation=%s "
                "time_to_first_chunk_seconds=%s "
                "total_generation_seconds=%.3f "
                "chunk_count=%d response_chars=%d",
                conversation_id,
                (
                    f"{time_to_first_chunk:.3f}"
                    if time_to_first_chunk is not None
                    else "n/a"
                ),
                total_generation_seconds,
                chunk_count,
                len(full_response),
            )

            # =================================================
            # 6. SEND COMPLETION EVENT
            # =================================================

            done_payload = {
                "type": "done",
                "message": {
                    "id": assistant_message.id,
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": full_response,
                },
            }

            if title_changed:
                done_payload["conversation"] = {
                    "id": conversation.id,
                    "title": conversation.title,
                }

            yield (
                "data: "
                + json.dumps(done_payload)
                + "\n\n"
            )

        except Exception as e:

            db.rollback()

            logger.exception(
                "conversation=%s streaming error: %s",
                conversation_id,
                e,
            )

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