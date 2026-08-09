"""Persisting and announcing a message, once, for every transport.

There were two implementations: the REST endpoint and the WebSocket handler. They
had drifted, and not harmlessly — the socket path skipped content filtering,
skipped flagging, skipped the audit record, never bumped the conversation's
updated_at, and sent no notification of any kind. A message sent over the socket
was invisible to moderation and left the conversation sitting stale at the bottom
of the other person's list.

That is the predictable result of writing the same behaviour twice, so it now
lives here and both transports call it. Anything added later — a new filter, a
new notification — lands on both by construction rather than by memory.
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Conversation, Message
from app.models.profile import Profile
from app.models.user import User
from app.services.audit import log_action
from app.services.content_filter import scan_text
from app.services.push import send_push

logger = logging.getLogger(__name__)

# Notification length. Long enough to be worth opening, short enough that a
# lock-screen preview doesn't spill a whole private message to anyone holding
# the phone.
PREVIEW_CHARS = 120


def preview(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"


def other_participant_id(conv: Conversation, my_profile_id: int) -> int | None:
    if conv.profile1_id == my_profile_id:
        return conv.profile2_id
    if conv.profile2_id == my_profile_id:
        return conv.profile1_id
    return None


async def persist_message(
    db: AsyncSession,
    conv: Conversation,
    sender_profile_id: int,
    content: str,
    request=None,
) -> Message:
    """Store a message with moderation applied, and commit.

    Returns the refreshed Message. Notification is deliberately separate: a
    caller that fails to notify must not lose the message.
    """
    flagged, matched = scan_text(content)

    message = Message(
        conversation_id=conv.id,
        sender_profile_id=sender_profile_id,
        content=content,
        is_flagged=flagged,
        flag_reason=matched,
    )
    db.add(message)

    if flagged:
        await log_action(
            db,
            actor_type="system",
            action="flag_message",
            resource_type="message",
            details={"matched_term": matched, "sender_profile_id": sender_profile_id},
            request=request,
        )

    # Without this the conversation stays where it was in the other person's
    # list, so a new message can arrive below week-old threads.
    conv.updated_at = func.now()

    await db.commit()
    await db.refresh(message)
    return message


async def notify_recipient(
    db: AsyncSession,
    conv: Conversation,
    sender_profile_id: int,
    sender_name: str,
    content: str,
) -> None:
    """Email and push the other participant. Never raises.

    A notification failure must not surface as a failure to send: the message is
    already stored, and telling someone their message failed when it didn't is
    worse than a missed notification.
    """
    try:
        other_pid = other_participant_id(conv, sender_profile_id)
        if not other_pid:
            return

        other_profile = (
            await db.execute(select(Profile).where(Profile.id == other_pid))
        ).scalar_one_or_none()
        if not other_profile:
            return

        other_user = (
            await db.execute(select(User).where(User.id == other_profile.user_id))
        ).scalar_one_or_none()
        if not other_user:
            return

        from app.services.email import send_new_message

        send_new_message(other_user.email, sender_name)
        await send_push(
            db,
            other_user.id,
            sender_name,
            preview(content),
            {"type": "message", "conversation_id": conv.id},
        )
        await db.commit()
    except Exception:
        logger.exception("[NOTIFY] new-message notification failed")
