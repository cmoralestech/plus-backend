"""Badge counts for nav items."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.match import Like, Match
from app.models.message import Message, Conversation
from sqlalchemy import or_

router = APIRouter(prefix="/api/badges", tags=["badges"])


@router.get("/")
async def get_badge_counts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        return {"unread_messages": 0, "likes_received": 0}

    pid = user.profile.id

    # Unread messages across all conversations
    conv_ids_result = await db.execute(
        select(Conversation.id)
        .join(Match, Conversation.match_id == Match.id)
        .where(or_(Match.profile1_id == pid, Match.profile2_id == pid))
    )
    conv_ids = [r[0] for r in conv_ids_result.all()]

    unread = 0
    if conv_ids:
        unread_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id.in_(conv_ids),
                Message.sender_profile_id != pid,
                Message.is_read == False,
            )
        )
        unread = unread_result.scalar() or 0

    # Likes received (not yet matched)
    likes_result = await db.execute(
        select(func.count(Like.id)).where(Like.to_profile_id == pid)
    )
    likes = likes_result.scalar() or 0

    return {"unread_messages": unread, "likes_received": likes}
