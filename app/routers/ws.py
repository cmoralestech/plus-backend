"""WebSocket endpoint for real-time messaging."""
import json
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

router = APIRouter()

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
        pass
    return None


async def verify_conversation_access(profile_id: int, conversation_id: int) -> bool:
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            if not conv:
                return False
            match = conv.match
            return profile_id in (match.profile1_id, match.profile2_id)
    except Exception:
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
                                pass

            elif msg.get("type") == "message":
                conv_id = msg.get("conversation_id")
                content = msg.get("content", "").strip()

                if not conv_id or not content or len(content) > 5000:
                    continue

                # Verify access
                has_access = await verify_conversation_access(profile_id, conv_id)
                if not has_access:
                    continue

                # Save message
                try:
                    async with async_session() as db:
                        message = Message(
                            conversation_id=conv_id,
                            sender_profile_id=profile_id,
                            content=content,
                        )
                        db.add(message)
                        await db.commit()
                        await db.refresh(message)

                        saved_msg = {
                            "type": "message",
                            "id": message.id,
                            "conversation_id": message.conversation_id,
                            "sender_profile_id": message.sender_profile_id,
                            "content": message.content,
                            "is_read": False,
                            "created_at": message.created_at.isoformat(),
                        }

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
                            pass

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        connections[profile_id].remove(websocket)
        if not connections[profile_id]:
            del connections[profile_id]
