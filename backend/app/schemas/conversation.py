from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    user_id : int
    title: str ="New Conversation"

class ConversationUpdate(BaseModel):
    title: str


class ConversationResponse(BaseModel):
    id: int
    user_id : int
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    