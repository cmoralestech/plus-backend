from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.profile import ProfileResponse


class LikeCreate(BaseModel):
    profile_id: int
    # Optional label for what prompted the like, surfaced to the recipient.
    context: str | None = Field(None, max_length=160)
    # A note sent alongside. Becomes the opening message on a mutual like.
    comment: str | None = Field(None, max_length=300)


class LikeResponse(BaseModel):
    id: int
    from_profile_id: int
    to_profile_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    id: int
    profile: ProfileResponse
    created_at: datetime
    has_conversation: bool = False
    last_message: str | None = None
    unread_count: int = 0

    model_config = {"from_attributes": True}
