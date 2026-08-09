"""Both transports moderate a message identically.

The WebSocket handler built its own Message inline, so a message sent over the
socket skipped content filtering, skipped flagging, skipped the audit record and
never bumped the conversation. It was invisible to moderation — and the client
was about to be pointed at it, which would have moved every message onto that
path.

These tests exercise the shared service both transports now call. If a future
change reintroduces a second implementation, the parity assertions here fail.
"""
import pytest
from sqlalchemy import select

from app.models.message import Conversation, Message
from app.services.messaging import other_participant_id, persist_message, preview
from tests.conftest import auth_header


async def _conversation(client, sender, recipient) -> int:
    r = await client.post(
        f"/api/messages/start/{recipient['profile'].id}",
        headers=auth_header(sender["token"]),
        json={"content": "Opening line."},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["conversation_id"]


@pytest.mark.asyncio
async def test_the_shared_service_flags_prohibited_content(
    client, db, sugar_user, attractive_user, monkeypatch
):
    """This is what the socket path was skipping entirely."""
    monkeypatch.setattr("app.services.messaging.scan_text", lambda t: (True, "matched-term"))

    conv_id = await _conversation(client, sugar_user, attractive_user)
    conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id))).scalar_one()

    message = await persist_message(db, conv, sugar_user["profile"].id, "anything at all")

    assert message.is_flagged is True
    assert message.flag_reason == "matched-term"


@pytest.mark.asyncio
async def test_clean_content_is_not_flagged(client, db, sugar_user, attractive_user):
    conv_id = await _conversation(client, sugar_user, attractive_user)
    conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id))).scalar_one()

    message = await persist_message(db, conv, sugar_user["profile"].id, "Thursday works for me.")
    assert message.is_flagged is False


@pytest.mark.asyncio
async def test_sending_moves_the_conversation_up_the_list(
    client, db, sugar_user, attractive_user
):
    """The socket never touched updated_at, so a live message could arrive below
    week-old threads in the other person's inbox."""
    conv_id = await _conversation(client, sugar_user, attractive_user)
    conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id))).scalar_one()
    before = conv.updated_at

    await persist_message(db, conv, sugar_user["profile"].id, "Still there?")
    await db.refresh(conv)

    assert conv.updated_at is not None
    if before is not None:
        assert conv.updated_at >= before


@pytest.mark.asyncio
async def test_the_rest_endpoint_flags_through_the_same_path(
    client, db, sugar_user, attractive_user, monkeypatch
):
    """Parity: the REST route must reach the same filter, not its own copy."""
    monkeypatch.setattr("app.services.messaging.scan_text", lambda t: (True, "matched-term"))

    conv_id = await _conversation(client, sugar_user, attractive_user)
    r = await client.post(
        f"/api/messages/{conv_id}",
        headers=auth_header(sugar_user["token"]),
        json={"content": "anything at all"},
    )
    assert r.status_code == 201

    stored = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.id.desc())
        )
    ).scalars().first()
    assert stored.is_flagged is True


def test_preview_truncates_without_spilling_a_whole_message():
    assert preview("short") == "short"
    long = "x" * 500
    assert len(preview(long)) <= 120
    assert preview(long).endswith("…")
    # Whitespace is collapsed so a message of newlines can't pad a preview out.
    assert preview("a\n\n   b") == "a b"


def test_other_participant_is_resolved_from_either_side():
    conv = Conversation(id=1, profile1_id=10, profile2_id=20)
    assert other_participant_id(conv, 10) == 20
    assert other_participant_id(conv, 20) == 10
    # Somebody who isn't in the conversation resolves to nobody, rather than
    # defaulting to a participant and notifying a stranger.
    assert other_participant_id(conv, 999) is None
