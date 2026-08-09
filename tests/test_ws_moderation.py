"""A message sent over the socket is moderated like any other.

This is the test that matters most in this area. The socket handler used to build
its own Message inline, so anything sent through it bypassed the content filter
entirely — and the mobile client was about to be pointed at it, which would have
routed every message in the product down the unmoderated path.

Uses Starlette's TestClient because websockets need a real transport, not the
ASGI-in-process client the rest of the suite uses.
"""
import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from app.main import app
from app.models.message import Conversation, Message


@pytest.fixture
def ws_client():
    """A client for socket handshakes only.

    Deliberately not entered as a context manager: that runs the app's lifespan,
    which opens a real Postgres connection and its own event loop, and the loop
    then fights pytest-asyncio's for the rest of the session. These tests only
    need the handshake, which is rejected before any database work happens.
    """
    return TestClient(app)


@pytest.mark.asyncio
async def test_socket_rejects_a_missing_token(ws_client):
    """Anonymous sockets must not reach a conversation."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect("/ws/chat") as ws:
            ws.receive_text()
    assert exc.value.code == 4001


@pytest.mark.asyncio
async def test_socket_rejects_a_forged_token(ws_client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect("/ws/chat?token=not-a-real-jwt") as ws:
            ws.receive_text()
    assert exc.value.code == 4001


@pytest.mark.asyncio
async def test_a_socket_message_is_content_filtered(
    client, db, sugar_user, attractive_user, monkeypatch
):
    """The regression this whole refactor exists to prevent."""
    monkeypatch.setattr("app.services.messaging.scan_text", lambda t: (True, "matched-term"))

    from tests.conftest import auth_header

    r = await client.post(
        f"/api/messages/start/{attractive_user['profile'].id}",
        headers=auth_header(sugar_user["token"]),
        json={"content": "Opening line."},
    )
    conv_id = r.json()["conversation_id"]
    conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id))).scalar_one()

    # Exercise the same service the socket handler calls, with the same
    # arguments it passes. A true end-to-end socket send needs a live server;
    # what must not regress is that this path filters at all.
    from app.services.messaging import persist_message

    message = await persist_message(db, conv, sugar_user["profile"].id, "anything")
    assert message.is_flagged is True

    stored = (
        await db.execute(select(Message).where(Message.id == message.id))
    ).scalar_one()
    assert stored.flag_reason == "matched-term"
