from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.services.image_storage import image_public_path


class MessageCreate(BaseModel):
    content: str


class MessageSource(BaseModel):
    source: str
    document_id: str | None = None


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    sources: list[dict[str, Any]] | None = None
    created_at: datetime

    # Read from the ORM row but not sent to clients; they get
    # `image_url` instead (below).
    image_filename: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def image_url(self) -> str | None:
        if not self.image_filename:
            return None

        return image_public_path(self.image_filename)

    model_config = ConfigDict(from_attributes=True)