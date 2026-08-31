from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    user_id: int
    title: str = "New Conversation"


class ConversationUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None


class ConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    is_pinned: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)