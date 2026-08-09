"""Notes attached to likes, and the conversation they seed.

The value of this feature is entirely in the seeding: a match that opens with
what each person actually said gives both of them something to answer. If that
silently stops working, the like still succeeds and the match still forms, so
nothing looks broken — the conversations just go quiet. Hence these tests.
"""
import pytest
from sqlalchemy import select

from app.models.match import Like, Match
from app.models.message import Conversation, Message
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_like_stores_context_and_comment(client, db, sugar_user, attractive_user):
    r = await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={
            "profile_id": attractive_user["profile"].id,
            "context": "your answer about Sunday markets",
            "comment": "Which market, though?",
        },
    )
    assert r.status_code == 201

    like = (
        await db.execute(
            select(Like).where(Like.from_profile_id == sugar_user["profile"].id)
        )
    ).scalar_one()
    assert like.context == "your answer about Sunday markets"
    assert like.comment == "Which market, though?"


@pytest.mark.asyncio
async def test_a_mutual_like_seeds_the_conversation_with_both_notes(
    client, db, sugar_user, attractive_user
):
    """The whole point: the pair start with what they each said, in order."""
    await client.post(
        "/api/matches/like",
        headers=auth_header(attractive_user["token"]),
        json={"profile_id": sugar_user["profile"].id, "comment": "You seem sane."},
    )
    r = await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id, "comment": "So do you."},
    )
    assert r.status_code == 201

    match = (await db.execute(select(Match))).scalar_one()
    conversation = (
        await db.execute(select(Conversation).where(Conversation.match_id == match.id))
    ).scalar_one()

    messages = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id)
        )
    ).scalars().all()

    assert [m.content for m in messages] == ["You seem sane.", "So do you."]
    # Attribution matters — a seeded message must come from whoever wrote it.
    assert messages[0].sender_profile_id == attractive_user["profile"].id
    assert messages[1].sender_profile_id == sugar_user["profile"].id


@pytest.mark.asyncio
async def test_a_match_without_notes_starts_empty(client, db, sugar_user, attractive_user):
    """Bare likes must not invent an opening message out of nothing."""
    await client.post(
        "/api/matches/like",
        headers=auth_header(attractive_user["token"]),
        json={"profile_id": sugar_user["profile"].id},
    )
    await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id},
    )

    messages = (await db.execute(select(Message))).scalars().all()
    assert messages == []


@pytest.mark.asyncio
async def test_a_note_is_content_filtered(client, sugar_user, attractive_user, monkeypatch):
    """A note is member-authored text reaching another member, so it goes through
    the same filter as a message rather than being trusted for being short."""
    monkeypatch.setattr(
        "app.routers.matches.scan_text", lambda text: (True, "matched-term")
    )

    r = await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id, "comment": "anything at all"},
    )
    assert r.status_code == 400
    assert "reword" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_a_blank_note_is_stored_as_absent(client, db, sugar_user, attractive_user):
    """Whitespace must not count as a note, or it seeds an empty message."""
    await client.post(
        "/api/matches/like",
        headers=auth_header(sugar_user["token"]),
        json={"profile_id": attractive_user["profile"].id, "comment": "   "},
    )

    like = (
        await db.execute(select(Like).where(Like.from_profile_id == sugar_user["profile"].id))
    ).scalar_one()
    assert like.comment is None
