"""WebSocket endpoint for real-time messaging."""
import json
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.user import User
from app.models.match import Match
from app.models.message import Conversation, Message
from app.models.profile import Profile
from app.services.messaging import notify_recipient, persist_message

router = APIRouter()
logger = logging.getLogger("plus.ws")

# Active connections: profile_id -> list of WebSocket connections
connections: dict[int, list[WebSocket]] = defaultdict(list)


async def authenticate_ws(token: str) -> int | None:
    """Verify JWT and return user_id, or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub else None
    except (JWTError, ValueError):
        return None


async def get_profile_id(user_id: int) -> int | None:
    try:
        async with async_session() as db:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            if user and user.profile:
                return user.profile.id
    except Exception:
        # Returning None here silently refuses the connection, so the reason
        # has to be recoverable from the logs.
        logger.exception("[WS] Failed to resolve profile for the connecting user")
    return None


async def verify_conversation_access(profile_id: int, conversation_id: int) -> bool:
    """Whether this member may use this conversation right now.

    Participation is read from the conversation itself rather than from its
    match. Conversations can exist without one — /start creates them directly —
    and going through match meant every one of those was refused, so live chat
    silently didn't work for anybody who hadn't matched first.
    """
    try:
        async with async_session() as db:
            conv = (
                await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
            ).scalar_one_or_none()
            if not conv:
                return False

            if profile_id not in (conv.profile1_id, conv.profile2_id):
                return False

            # An ended match closes the conversation on every transport. Without
            # this, unmatching stopped the REST routes but left the socket open.
            if conv.match_id:
                match = (
                    await db.execute(select(Match).where(Match.id == conv.match_id))
                ).scalar_one_or_none()
                if not match or not match.is_active:
                    return False

            return True
    except Exception:
        logger.exception("[WS] Access check failed for conversation %s", conversation_id)
        return False


async def get_other_profile_id(conversation_id: int, my_profile_id: int) -> int | None:
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            if not conv:
                return None
            match = conv.match
            return match.profile2_id if match.profile1_id == my_profile_id else match.profile1_id
    except Exception:
        return None


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()

    # Authenticate via query param token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    user_id = await authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    profile_id = await get_profile_id(user_id)
    if not profile_id:
        await websocket.close(code=4002, reason="No profile")
        return

    # Register connection
    connections[profile_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "typing":
                conv_id = msg.get("conversation_id")
                if conv_id:
                    other_pid = await get_other_profile_id(conv_id, profile_id)
                    if other_pid and other_pid in connections:
                        typing_event = json.dumps({
                            "type": "typing",
                            "conversation_id": conv_id,
                            "profile_id": profile_id,
                        })
                        for ws in connections[other_pid]:
                            try:
                                await ws.send_text(typing_event)
                            except Exception:
                                # Peer socket already closed. Normal, and far
                                # too frequent to be worth logging.
                                pass

            elif msg.get("type") == "message":
                conv_id = msg.get("conversation_id")
                content = msg.get("content", "").strip()

                if not conv_id or not content or len(content) > 5000:
                    continue

                # Verify access. Refusing silently used to drop the message
                # with no acknowledgement of any kind: a client that had already
                # handed it to the socket would wait forever for an echo that
                # was never coming, and the message was simply lost.
                has_access = await verify_conversation_access(profile_id, conv_id)
                if not has_access:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "conversation_id": conv_id,
                        "message": "This conversation is no longer available.",
                    }))
                    continue

                # Save message. This used to build a Message inline, which
                # meant the socket skipped content filtering, flagging, the
                # audit record, updated_at and every notification — a message
                # sent this way was invisible to moderation. Both transports
                # now go through the same service.
                try:
                    async with async_session() as db:
                        conv = (
                            await db.execute(
                                select(Conversation).where(Conversation.id == conv_id)
                            )
                        ).scalar_one_or_none()
                        if not conv:
                            continue

                        sender = (
                            await db.execute(
                                select(Profile).where(Profile.id == profile_id)
                            )
                        ).scalar_one_or_none()

                        message = await persist_message(db, conv, profile_id, content)

                        saved_msg = {
                            "type": "message",
                            "id": message.id,
                            "conversation_id": message.conversation_id,
                            "sender_profile_id": message.sender_profile_id,
                            "content": message.content,
                            "is_read": False,
                            "created_at": message.created_at.isoformat(),
                        }

                        await notify_recipient(
                            db,
                            conv,
                            profile_id,
                            sender.display_name if sender else "Someone",
                            content,
                        )

                    # Send to sender
                    await websocket.send_text(json.dumps(saved_msg))
                except Exception:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Failed to send message. Please try again."}))
                    continue

                # Send to recipient if online
                other_pid = await get_other_profile_id(conv_id, profile_id)
                if other_pid and other_pid in connections:
                    for ws in connections[other_pid]:
                        try:
                            await ws.send_text(json.dumps(saved_msg))
                        except Exception:
                            # Peer socket already closed; the message is
                            # persisted and will load on reconnect.
                            pass

    except WebSocketDisconnect:
        pass  # Ordinary client disconnect.
    except Exception:
        # Anything else is a bug in the socket loop. Swallowing it silently
        # made every such bug look like a normal disconnect.
        logger.exception("[WS] Connection loop failed for profile %s", profile_id)
    finally:
        connections[profile_id].remove(websocket)
        if not connections[profile_id]:
            del connections[profile_id]
