from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.profile import ProfileResponse


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_profile_id: int
    sender_name: str | None = None
    content: str
    is_read: bool
    created_at: datetime
    locked: bool = False  # True if content is hidden behind paywall

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: int
    match_id: int
    other_profile: ProfileResponse | None = None
    last_message: MessageResponse | None = None
    unread_count: int = 0
    can_read: bool = True  # Whether the user can read messages in this conversation
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
