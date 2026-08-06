"""Admin profile and photo management.

Editing someone else's profile and adding photos to their account are the two
most consequential things an administrator can do here, so the guarantees
worth pinning are: only safe fields are editable, admin uploads are screened
like anyone else's, and every action leaves an audit entry.
"""
import io

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.audit import AuditLog
from app.models.profile import Photo
from tests.conftest import auth_header


@pytest.fixture
def as_admin(monkeypatch, sugar_user):
    monkeypatch.setattr("app.routers.admin.ADMIN_EMAILS", {sugar_user["user"].email})
    return sugar_user


def _jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 400), (120, 150, 180)).save(buf, format="JPEG")
    return buf.getvalue()


class TestProfileEditing:
    @pytest.mark.asyncio
    async def test_edits_allowed_fields(self, client, db, as_admin):
        pid = as_admin["profile"].id
        r = await client.patch(
            f"/api/admin/profiles/{pid}",
            json={"headline": "Corrected headline"},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 200, r.text
        assert r.json()["updated"] is True

        await db.refresh(as_admin["profile"])
        assert as_admin["profile"].headline == "Corrected headline"

    @pytest.mark.asyncio
    async def test_refuses_fields_with_legal_or_billing_meaning(self, client, as_admin):
        """Date of birth backs the 18+ guarantee. It is not a text box."""
        pid = as_admin["profile"].id
        r = await client.patch(
            f"/api/admin/profiles/{pid}",
            json={"date_of_birth": "2010-01-01"},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 400
        assert "date_of_birth" in r.text

    @pytest.mark.asyncio
    async def test_edit_is_audited_with_before_and_after(self, client, db, as_admin):
        pid = as_admin["profile"].id
        await client.patch(
            f"/api/admin/profiles/{pid}",
            json={"bio": "Rewritten by an administrator"},
            headers=auth_header(as_admin["token"]),
        )
        entry = (await db.execute(
            select(AuditLog).where(AuditLog.action == "admin_edit_profile")
        )).scalars().first()
        assert entry is not None
        assert "bio" in str(entry.details)

    @pytest.mark.asyncio
    async def test_admin_text_is_rescreened(self, client, db, as_admin):
        """An admin shouldn't be able to publish what a member couldn't."""
        pid = as_admin["profile"].id
        r = await client.patch(
            f"/api/admin/profiles/{pid}",
            json={"bio": "full service incall available"},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 200
        assert r.json()["is_flagged"] is True

    @pytest.mark.asyncio
    async def test_unchanged_values_are_a_no_op(self, client, as_admin):
        pid = as_admin["profile"].id
        current = as_admin["profile"].display_name
        r = await client.patch(
            f"/api/admin/profiles/{pid}",
            json={"display_name": current},
            headers=auth_header(as_admin["token"]),
        )
        assert r.json()["updated"] is False

    @pytest.mark.asyncio
    async def test_requires_admin(self, client, sugar_user, monkeypatch):
        monkeypatch.setattr("app.routers.admin.ADMIN_EMAILS", {"someone.else@example.com"})
        r = await client.patch(
            f"/api/admin/profiles/{sugar_user['profile'].id}",
            json={"headline": "nope"},
            headers=auth_header(sugar_user["token"]),
        )
        assert r.status_code == 403


class TestAdminPhotoUpload:
    @pytest.mark.asyncio
    async def test_upload_is_screened_like_a_member_upload(
        self, client, db, as_admin, monkeypatch
    ):
        """The admin route must not be a way around content screening."""
        from app.services import image_moderation
        from app.services.image_moderation import Action, Verdict

        async def blocked(_contents):
            return Verdict(action=Action.REJECT, top_label="Explicit", top_confidence=97.0)

        monkeypatch.setattr(image_moderation, "scan_image", blocked)

        r = await client.post(
            f"/api/admin/profiles/{as_admin['profile'].id}/photos",
            files={"file": ("x.jpg", _jpeg(), "image/jpeg")},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 400
        assert "screening" in r.text.lower()

    @pytest.mark.asyncio
    async def test_clean_upload_is_stored_and_audited(self, client, db, as_admin):
        pid = as_admin["profile"].id
        r = await client.post(
            f"/api/admin/profiles/{pid}/photos",
            files={"file": ("x.jpg", _jpeg(), "image/jpeg")},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 201, r.text
        assert r.json()["pending_review"] is False

        photo = (await db.execute(select(Photo).where(Photo.profile_id == pid))).scalars().first()
        assert photo is not None
        assert photo.is_primary is True  # first photo becomes primary

        entry = (await db.execute(
            select(AuditLog).where(AuditLog.action == "admin_upload_photo")
        )).scalars().first()
        assert entry is not None

    @pytest.mark.asyncio
    async def test_rejects_non_images(self, client, as_admin):
        r = await client.post(
            f"/api/admin/profiles/{as_admin['profile'].id}/photos",
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 400


class TestAdminPhotoDeletion:
    @pytest.mark.asyncio
    async def test_delete_removes_the_file_too(self, client, db, as_admin, monkeypatch):
        from app.services import storage as storage_module

        deleted: list[str] = []

        async def fake_delete(filename):
            deleted.append(filename)
            return True

        monkeypatch.setattr(storage_module.storage, "delete", fake_delete)

        photo = Photo(profile_id=as_admin["profile"].id, url="/uploads/a.jpg", order=0)
        db.add(photo)
        await db.commit()
        await db.refresh(photo)

        r = await client.delete(
            f"/api/admin/photos/{photo.id}", headers=auth_header(as_admin["token"])
        )
        assert r.status_code == 200
        assert deleted == ["a.jpg"]

    @pytest.mark.asyncio
    async def test_held_photo_cannot_be_made_primary(self, client, db, as_admin):
        photo = Photo(
            profile_id=as_admin["profile"].id, url="/uploads/held.jpg",
            order=0, is_flagged=True, moderation_status="flagged",
        )
        db.add(photo)
        await db.commit()
        await db.refresh(photo)

        r = await client.post(
            f"/api/admin/photos/{photo.id}/primary",
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 400
