from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    user_id: int
    document_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)