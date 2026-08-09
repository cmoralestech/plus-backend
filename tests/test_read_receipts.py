"""hide_read_receipts is actually enforced.

The setting existed, was settable through the API, and was read by nothing. It
looked harmless because no client displayed receipts — so the moment one did, a
member who had switched it on would start telling the other person exactly what
they had asked us not to. A privacy control that silently does nothing is worse
than not offering it.
"""
import pytest
from sqlalchemy import select

from app.models.message import Conversation, Message
from app.models.subscription import PrivacySettings
from tests.conftest import auth_header


async def _conversation(client, db, sender, recipient, text="Are you around Thursday?"):
    """Sender messages recipient, recipient reads it. Returns the conversation id."""
    r = await client.post(
        f"/api/messages/start/{recipient['profile'].id}",
        headers=auth_header(sender["token"]),
        json={"content": text},
    )
    assert r.status_code in (200, 201), r.text
    conv_id = r.json()["conversation_id"]

    # Opening the conversation is what marks it read.
    await client.get(f"/api/messages/{conv_id}", headers=auth_header(recipient["token"]))
    return conv_id


@pytest.mark.asyncio
async def test_the_sender_sees_a_receipt_by_default(client, db, sugar_user, attractive_user):
    conv_id = await _conversation(client, db, sugar_user, attractive_user)

    msgs = (await client.get(f"/api/messages/{conv_id}", headers=auth_header(sugar_user["token"]))).json()
    mine = [m for m in msgs if m["sender_profile_id"] == sugar_user["profile"].id]
    assert mine and mine[-1]["is_read"] is True


@pytest.mark.asyncio
async def test_hiding_receipts_stops_the_sender_seeing_them(
    client, db, sugar_user, attractive_user
):
    """The whole point. The reader's setting governs, not the sender's."""
    db.add(PrivacySettings(user_id=attractive_user["user"].id, hide_read_receipts=True))
    await db.commit()

    conv_id = await _conversation(client, db, sugar_user, attractive_user)

    msgs = (await client.get(f"/api/messages/{conv_id}", headers=auth_header(sugar_user["token"]))).json()
    mine = [m for m in msgs if m["sender_profile_id"] == sugar_user["profile"].id]
    assert mine and mine[-1]["is_read"] is False


@pytest.mark.asyncio
async def test_the_message_is_still_marked_read_underneath(
    client, db, sugar_user, attractive_user
):
    """Hiding the receipt must not stop unread counts working for the reader —
    it withholds the signal from the sender, it doesn't stop tracking."""
    db.add(PrivacySettings(user_id=attractive_user["user"].id, hide_read_receipts=True))
    await db.commit()

    conv_id = await _conversation(client, db, sugar_user, attractive_user)

    stored = (
        await db.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.sender_profile_id == sugar_user["profile"].id,
            )
        )
    ).scalars().all()
    assert stored and all(m.is_read for m in stored)


@pytest.mark.asyncio
async def test_hiding_my_receipts_does_not_hide_the_other_persons_messages(
    client, db, sugar_user, attractive_user
):
    """The setting is about what I reveal, not what I can see. Someone who hides
    their own receipts must still get a working inbox."""
    db.add(PrivacySettings(user_id=attractive_user["user"].id, hide_read_receipts=True))
    await db.commit()

    conv_id = await _conversation(client, db, sugar_user, attractive_user)

    msgs = (await client.get(f"/api/messages/{conv_id}", headers=auth_header(attractive_user["token"]))).json()
    assert len(msgs) >= 1
    assert all(m["content"] for m in msgs)
