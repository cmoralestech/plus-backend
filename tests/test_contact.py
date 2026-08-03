"""Contact form durability.

The form tells the sender "we'll get back to you within 24 hours". That promise
has to survive email being broken, which it was — the domain had no MX record,
so every submission was emailed into a void and stored nowhere.
"""
import pytest
from sqlalchemy import select

from app.models.contact import ContactSubmission

PAYLOAD = {
    "name": "Test Person",
    "email": "someone@example.com",
    "category": "billing",
    "message": "I was charged twice for the same month and would like a refund.",
}


class TestPersistence:
    @pytest.mark.asyncio
    async def test_submission_is_stored(self, client, db):
        r = await client.post("/api/contact", json=PAYLOAD)
        assert r.status_code == 200

        row = (await db.execute(select(ContactSubmission))).scalars().first()
        assert row is not None
        assert row.email == "someone@example.com"
        assert row.category == "Billing & Subscription"
        assert row.message.startswith("I was charged twice")

    @pytest.mark.asyncio
    async def test_submission_survives_email_failure(self, client, db, monkeypatch):
        """The message must be kept even when nothing can be delivered."""
        def explode(**kwargs):
            raise RuntimeError("no MX record for meetyourplus.com")

        monkeypatch.setattr("app.routers.contact.send_contact_form", explode)

        r = await client.post("/api/contact", json=PAYLOAD)
        assert r.status_code == 200, r.text

        row = (await db.execute(select(ContactSubmission))).scalars().first()
        assert row is not None
        assert row.notified is False

    @pytest.mark.asyncio
    async def test_successful_send_marks_notified(self, client, db, monkeypatch):
        monkeypatch.setattr("app.routers.contact.send_contact_form", lambda **kw: None)

        await client.post("/api/contact", json=PAYLOAD)

        row = (await db.execute(select(ContactSubmission))).scalars().first()
        assert row.notified is True

    @pytest.mark.asyncio
    async def test_confirmation_failure_does_not_lose_the_message(
        self, client, db, monkeypatch
    ):
        monkeypatch.setattr("app.routers.contact.send_contact_form", lambda **kw: None)
        monkeypatch.setattr(
            "app.routers.contact.send_contact_confirmation",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("bounce")),
        )

        r = await client.post("/api/contact", json=PAYLOAD)
        assert r.status_code == 200
        assert (await db.execute(select(ContactSubmission))).scalars().first() is not None


class TestValidation:
    @pytest.mark.asyncio
    async def test_short_message_is_rejected(self, client):
        r = await client.post("/api/contact", json={**PAYLOAD, "message": "hi"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_bad_email_is_rejected(self, client):
        r = await client.post("/api/contact", json={**PAYLOAD, "email": "not-an-email"})
        assert r.status_code == 422
