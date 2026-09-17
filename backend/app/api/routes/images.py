from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.image_service import (
    ImageGenerationError,
    ImageGenerationQuotaExceededError,
    image_service,
)


logger = get_logger(__name__)


router = APIRouter(
    prefix="/images",
    tags=["Images"],
)


class ImageGenerateRequest(BaseModel):
    prompt: str
    conversation_id: int | None = None


class ImageGenerateResponse(BaseModel):
    image_base64: str
    mime_type: str
    text: str | None = None
    message_id: int | None = None


@router.post(
    "/generate",
    response_model=ImageGenerateResponse,
)
def generate_image(
    data: ImageGenerateRequest,
    db: Session = Depends(get_db),
):
    if not data.prompt or not data.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Please describe the image you want.",
        )

    try:
        result = image_service.generate_image(data.prompt)
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

    message_id = None

    # If this generation happened inside an existing
    # conversation, save it as an assistant message so it shows
    # up in history — same as a normal chat response, just with
    # an image data URI as the "content".
    if data.conversation_id is not None:

        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == data.conversation_id)
            .first()
        )

        if conversation is not None:

            data_uri = (
                f"data:{result['mime_type']};base64,"
                f"{result['image_base64']}"
            )

            content = f"![Generated image]({data_uri})"

            if result.get("text"):
                content = f"{result['text']}\n\n{content}"

            assistant_message = Message(
                conversation_id=data.conversation_id,
                role="assistant",
                content=content,
            )

            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

            message_id = assistant_message.id

    logger.info(
        "Image generated successfully, conversation_id=%s "
        "message_id=%s",
        data.conversation_id,
        message_id,
    )

    return ImageGenerateResponse(
        image_base64=result["image_base64"],
        mime_type=result["mime_type"],
        text=result.get("text"),
        message_id=message_id,
    )