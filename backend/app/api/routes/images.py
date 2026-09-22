import base64
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.routes.message import (
    DEFAULT_CONVERSATION_TITLE,
    generate_conversation_title,
)
from app.core.config import settings
from app.core.database import get_db, utc_now
from app.core.logging_config import get_logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.image_service import (
    ImageGenerationError,
    ImageGenerationQuotaExceededError,
    image_service,
)
from app.services.image_storage import (
    delete_image_files,
    image_public_path,
    resolve_image_file,
    save_image,
)


logger = get_logger(__name__)


router = APIRouter(
    prefix="/images",
    tags=["Images"],
)


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=settings.max_image_prompt_chars,
    )
    conversation_id: int | None = None


class ConversationRef(BaseModel):
    id: int
    title: str


class ImageGenerateResponse(BaseModel):
    # Exactly one of image_url / image_base64 is set:
    #  - image_url: the image was stored and attached to a
    #    conversation (the normal case).
    #  - image_base64: no conversation was given, so nothing was
    #    stored (avoids orphaned files); the image is returned inline.
    image_url: str | None = None
    image_base64: str | None = None
    mime_type: str
    text: str | None = None
    message_id: int | None = None

    # Only present when this request renamed the conversation
    # (first message), so the UI can update the sidebar.
    conversation: ConversationRef | None = None


# ============================================================
# GENERATE
# ============================================================

@router.post(
    "/generate",
    response_model=ImageGenerateResponse,
)
def generate_image(
    data: ImageGenerateRequest,
    db: Session = Depends(get_db),
):
    prompt = data.prompt.strip()

    if not prompt:
        raise HTTPException(
            status_code=400,
            detail="Please describe the image you want.",
        )

    # --------------------------------------------------------
    # 1. Validate the conversation BEFORE paying for a
    #    generation — an unknown id used to be silently ignored,
    #    so the client thought the image was saved.
    # --------------------------------------------------------

    conversation: Conversation | None = None
    is_first_message = False

    if data.conversation_id is not None:

        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == data.conversation_id)
            .first()
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        is_first_message = (
            db.query(Message.id)
            .filter(Message.conversation_id == conversation.id)
            .first()
            is None
        )

    # Generation takes 10-30s. End the read transaction now so this
    # request doesn't hold a pooled DB connection the whole time.
    db.rollback()

    # --------------------------------------------------------
    # 2. Generate
    # --------------------------------------------------------

    try:
        result = image_service.generate_image(prompt)
    except ImageGenerationQuotaExceededError as e:
        raise HTTPException(
            status_code=429,
            detail=str(e),
        )
    except ImageGenerationError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(
            "Unexpected image generation failure: %s", e
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Image generation is temporarily unavailable. "
                "Please try again."
            ),
        )

    mime_type = result["mime_type"]
    caption = result.get("text")

    # --------------------------------------------------------
    # 3a. No conversation: nothing to attach to, so don't store
    #     anything. Return the image inline.
    # --------------------------------------------------------

    if conversation is None:
        logger.info("Image generated (not attached to a conversation)")

        return ImageGenerateResponse(
            image_base64=result["image_base64"],
            mime_type=mime_type,
            text=caption,
        )

    # --------------------------------------------------------
    # 3b. Store the file, then save the prompt and the image
    #     message in ONE transaction. If the database write
    #     fails the file is removed again, so we never leave an
    #     image with no message pointing at it.
    # --------------------------------------------------------

    filename = save_image(
        base64.b64decode(result["image_base64"]),
        mime_type,
    )

    # Explicit, ordered timestamps: two rows inserted in one flush
    # could otherwise share a timestamp and come back in either order.
    created_at = utc_now()

    user_message = Message(
        conversation_id=data.conversation_id,
        role="user",
        content=prompt,
        created_at=created_at,
    )

    assistant_message = Message(
        conversation_id=data.conversation_id,
        role="assistant",
        content=caption or "",
        image_filename=filename,
        created_at=created_at + timedelta(milliseconds=1),
    )

    title_changed = False

    try:
        db.add_all([user_message, assistant_message])

        if (
            is_first_message
            and conversation.title == DEFAULT_CONVERSATION_TITLE
        ):
            conversation.title = generate_conversation_title(prompt)
            title_changed = True

        db.commit()

    except (IntegrityError, StaleDataError):
        # The conversation was deleted while the image was generating
        # (FK violation on insert, or 0 rows matched on the rename).
        db.rollback()
        delete_image_files([filename])

        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    except Exception as e:
        db.rollback()
        delete_image_files([filename])

        logger.exception(
            "Could not save generated image, conversation_id=%s: %s",
            data.conversation_id,
            e,
        )

        raise HTTPException(
            status_code=503,
            detail="Could not save the generated image. Please try again.",
        )

    db.refresh(assistant_message)
    db.refresh(conversation)

    logger.info(
        "Image generated, conversation_id=%s message_id=%s",
        data.conversation_id,
        assistant_message.id,
    )

    return ImageGenerateResponse(
        image_url=image_public_path(filename),
        mime_type=mime_type,
        text=caption,
        message_id=assistant_message.id,
        conversation=(
            ConversationRef(
                id=data.conversation_id,
                title=conversation.title,
            )
            if title_changed
            else None
        ),
    )


# ============================================================
# SERVE A STORED IMAGE
# ============================================================

@router.get("/files/{filename}")
def get_image_file(filename: str):
    path = resolve_image_file(filename)

    if path is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found",
        )

    # Filenames are random and never reused, so the content behind
    # a URL never changes: safe to cache for a year. `private` keeps
    # shared proxies from caching user content.
    return FileResponse(
        path,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
