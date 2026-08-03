"""Automated photo screening.

The classifier itself belongs to AWS; what we test is our policy around it —
which labels reject vs. hold, that an outage fails closed rather than open, and
that a held photo is genuinely invisible rather than merely marked.
"""
import pytest

from app.config import settings
from app.services import image_moderation
from app.services.image_moderation import Action, Verdict


def _label(name, confidence, parent=None):
    return {"Name": name, "Confidence": confidence, "ParentName": parent}


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_MODERATION_PROVIDER", "rekognition")
    monkeypatch.setattr(settings, "IMAGE_MODERATION_REJECT_THRESHOLD", 80.0)
    monkeypatch.setattr(settings, "IMAGE_MODERATION_FLAG_THRESHOLD", 55.0)
    monkeypatch.setattr(settings, "IMAGE_MODERATION_FAIL_CLOSED", True)


class TestClassification:
    def test_clean_image_passes(self, enabled):
        assert image_moderation._classify([]).action == Action.PASS

    def test_confident_explicit_content_is_rejected(self, enabled):
        v = image_moderation._classify([_label("Sexual Activity", 96.4, "Explicit")])
        assert v.action == Action.REJECT
        assert v.top_label == "Sexual Activity"

    def test_uncertain_explicit_content_is_held_not_rejected(self, enabled):
        """Below the reject threshold a person decides, not the classifier."""
        v = image_moderation._classify([_label("Sexual Activity", 61.0, "Explicit")])
        assert v.action == Action.FLAG

    def test_borderline_nudity_is_held(self, enabled):
        v = image_moderation._classify(
            [_label("Female Swimwear Or Underwear", 70.0,
                    "Non-Explicit Nudity of Intimate parts and Kissing")]
        )
        assert v.action == Action.FLAG

    def test_swimwear_alone_is_allowed(self, enabled):
        """A beach photo is ordinary on a dating profile — flagging it would
        bury the queue in noise and teach reviewers to click through."""
        v = image_moderation._classify(
            [_label("Swimwear", 99.0, "Swimwear or Underwear")]
        )
        assert v.action == Action.PASS

    def test_alcohol_and_gambling_are_allowed(self, enabled):
        v = image_moderation._classify([
            _label("Alcoholic Beverages", 97.0, "Alcohol"),
            _label("Gambling", 91.0, "Gambling"),
        ])
        assert v.action == Action.PASS

    def test_violence_is_rejected(self, enabled):
        v = image_moderation._classify([_label("Weapon Violence", 88.0, "Violence")])
        assert v.action == Action.REJECT

    def test_reject_outranks_flag_in_the_same_image(self, enabled):
        v = image_moderation._classify([
            _label("Rude Gestures", 99.0, "Rude Gestures"),
            _label("Sexual Activity", 85.0, "Explicit"),
        ])
        assert v.action == Action.REJECT
        assert v.top_label == "Sexual Activity"

    def test_low_confidence_noise_is_ignored(self, enabled):
        v = image_moderation._classify([_label("Sexual Activity", 20.0, "Explicit")])
        assert v.action == Action.PASS


@pytest.fixture
def sightengine(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_MODERATION_PROVIDER", "sightengine")
    monkeypatch.setattr(settings, "SIGHTENGINE_API_USER", "u")
    monkeypatch.setattr(settings, "SIGHTENGINE_API_SECRET", "s")
    monkeypatch.setattr(settings, "IMAGE_MODERATION_REJECT_THRESHOLD", 80.0)
    monkeypatch.setattr(settings, "IMAGE_MODERATION_FLAG_THRESHOLD", 55.0)


def _nudity(**scores):
    base = {
        "sexual_activity": 0.0, "sexual_display": 0.0, "erotica": 0.0,
        "very_suggestive": 0.0, "suggestive": 0.0, "mildly_suggestive": 0.0,
        "none": 1.0,
    }
    base.update(scores)
    return {"status": "success", "nudity": base}


class TestSightengineMapping:
    """Sightengine scores are 0-1 and cumulative; ours are 0-100 and ranked."""

    def test_scores_are_rescaled_to_percent(self, sightengine):
        labels = image_moderation._sightengine_labels(_nudity(sexual_activity=0.93))
        assert labels[0]["Confidence"] == pytest.approx(93.0)

    def test_explicit_content_rejects(self, sightengine):
        v = image_moderation._classify(
            image_moderation._sightengine_labels(_nudity(sexual_display=0.91))
        )
        assert v.action == Action.REJECT

    def test_only_the_most_severe_nudity_tier_is_reported(self, sightengine):
        """An erotica image also scores high on every tier beneath it. Emitting
        all of them would bury the real reason in noise."""
        labels = image_moderation._sightengine_labels(
            _nudity(erotica=0.88, very_suggestive=0.95, suggestive=0.98,
                    mildly_suggestive=0.99)
        )
        nudity_labels = [l for l in labels if l["ParentName"] in (
            "Explicit", "Non-Explicit Nudity of Intimate parts and Kissing")]
        assert len(nudity_labels) == 1
        assert nudity_labels[0]["Name"] == "Erotica"

    def test_undressed_is_held_not_rejected(self, sightengine):
        v = image_moderation._classify(
            image_moderation._sightengine_labels(_nudity(very_suggestive=0.90))
        )
        assert v.action == Action.FLAG

    def test_swimwear_and_cleavage_are_allowed(self, sightengine):
        """bikini/lingerie/cleavage live under suggestive, which we ignore."""
        payload = _nudity(suggestive=0.97, mildly_suggestive=0.99)
        payload["nudity"]["suggestive_classes"] = {"bikini": 0.95, "cleavage": 0.8}
        v = image_moderation._classify(image_moderation._sightengine_labels(payload))
        assert v.action == Action.PASS

    def test_clean_image_produces_no_labels(self, sightengine):
        assert image_moderation._sightengine_labels(_nudity()) == []

    def test_gore_rejects(self, sightengine):
        payload = _nudity()
        payload["gore"] = {"prob": 0.92}
        v = image_moderation._classify(image_moderation._sightengine_labels(payload))
        assert v.action == Action.REJECT

    def test_hate_symbols_reject_and_rude_gestures_flag(self, sightengine):
        payload = _nudity()
        payload["offensive"] = {"nazi": 0.95, "middle_finger": 0.0}
        assert image_moderation._classify(
            image_moderation._sightengine_labels(payload)
        ).action == Action.REJECT

        payload["offensive"] = {"nazi": 0.0, "middle_finger": 0.88}
        assert image_moderation._classify(
            image_moderation._sightengine_labels(payload)
        ).action == Action.FLAG

    @pytest.mark.asyncio
    async def test_missing_keys_disable_screening(self, sightengine, monkeypatch):
        monkeypatch.setattr(settings, "SIGHTENGINE_API_SECRET", "")
        assert "SIGHTENGINE" in image_moderation.misconfiguration()
        verdict = await image_moderation.scan_image(b"x")
        assert verdict.action == Action.UNSCANNED

    @pytest.mark.asyncio
    async def test_api_error_response_fails_closed(self, sightengine, monkeypatch):
        async def bad(_contents):
            raise RuntimeError("sightengine: invalid api_secret")

        monkeypatch.setattr(image_moderation, "_scan_sightengine", bad)
        verdict = await image_moderation.scan_image(b"x")
        assert verdict.action == Action.ERROR
        status, hidden, _ = image_moderation.resolve_outcome(verdict)
        assert hidden is True


class TestOutcomePolicy:
    def test_scan_error_is_held_when_failing_closed(self, enabled):
        status, hidden, reason = image_moderation.resolve_outcome(
            Verdict(action=Action.ERROR, error="timeout")
        )
        assert status == Action.FLAG
        assert hidden is True
        assert "timeout" in reason

    def test_scan_error_passes_through_when_failing_open(self, enabled, monkeypatch):
        monkeypatch.setattr(settings, "IMAGE_MODERATION_FAIL_CLOSED", False)
        status, hidden, _ = image_moderation.resolve_outcome(
            Verdict(action=Action.ERROR, error="timeout")
        )
        assert status == Action.ERROR
        assert hidden is False

    def test_clean_image_is_not_hidden(self, enabled):
        _, hidden, reason = image_moderation.resolve_outcome(Verdict(action=Action.PASS))
        assert hidden is False
        assert reason is None


class TestDisabledByDefault:
    @pytest.mark.asyncio
    async def test_unconfigured_provider_does_not_scan(self):
        """No credentials means the platform behaves exactly as before."""
        assert image_moderation.is_enabled() is False
        verdict = await image_moderation.scan_image(b"whatever")
        assert verdict.action == Action.UNSCANNED
        assert verdict.blocks_upload is False
        assert verdict.needs_review is False

    @pytest.mark.asyncio
    async def test_unknown_provider_disables_screening_loudly(self, monkeypatch):
        """A permanent config error must not fail closed. Failing closed on a
        working provider's bad minute is a backlog; failing closed on a
        misconfiguration holds every upload forever and looks like a broken
        product. It is logged at ERROR instead."""
        monkeypatch.setattr(settings, "IMAGE_MODERATION_PROVIDER", "not-a-provider")
        verdict = await image_moderation.scan_image(b"whatever")
        assert verdict.action == Action.UNSCANNED
        assert "not-a-provider" in verdict.error

    @pytest.mark.asyncio
    async def test_tigris_credentials_are_not_used_for_rekognition(
        self, enabled, monkeypatch
    ):
        """Object storage is Tigris, which publishes AWS_*-named keys that
        authenticate only against Tigris. Picking them up would fail auth on
        every upload."""
        monkeypatch.setattr(settings, "IMAGE_MODERATION_ACCESS_KEY_ID", "")
        monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://fly.storage.tigris.dev")

        assert "Rekognition" in image_moderation.misconfiguration()
        verdict = await image_moderation.scan_image(b"whatever")
        assert verdict.action == Action.UNSCANNED

    @pytest.mark.asyncio
    async def test_dedicated_credentials_clear_the_misconfiguration(
        self, enabled, monkeypatch
    ):
        monkeypatch.setattr(settings, "IMAGE_MODERATION_ACCESS_KEY_ID", "AKIAREAL")
        monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://fly.storage.tigris.dev")
        assert image_moderation.misconfiguration() is None

    @pytest.mark.asyncio
    async def test_provider_exception_becomes_error_not_a_500(self, enabled, monkeypatch):
        def boom(_contents):
            raise RuntimeError("credentials expired")

        monkeypatch.setattr(image_moderation, "_scan_rekognition", boom)
        verdict = await image_moderation.scan_image(b"whatever")
        assert verdict.action == Action.ERROR
        assert verdict.error == "RuntimeError"


class TestVisibility:
    @pytest.mark.asyncio
    async def test_flagged_photo_is_hidden_from_the_profile_response(
        self, client, db, sugar_user
    ):
        from app.models.profile import Photo
        from tests.conftest import auth_header

        profile_id = sugar_user["profile"].id
        db.add_all([
            Photo(profile_id=profile_id, url="/clean.jpg", order=0, is_primary=True),
            Photo(
                profile_id=profile_id, url="/held.jpg", order=1,
                is_flagged=True, flag_reason="Explicit (91%)",
                moderation_status="flagged",
            ),
        ])
        await db.commit()

        r = await client.get("/api/profiles/me", headers=auth_header(sugar_user["token"]))
        assert r.status_code == 200
        urls = [p["url"] for p in r.json()["photos"]]
        assert "/clean.jpg" in urls
        assert "/held.jpg" not in urls

    def test_is_visible_tracks_the_flag(self):
        from app.models.profile import Photo

        assert Photo(is_flagged=False).is_visible is True
        assert Photo(is_flagged=True).is_visible is False

    def test_held_photos_do_not_earn_ranking_credit(self, sugar_user):
        """A profile whose only photos are held looks empty to other members,
        so it must not rank as though it had photos."""
        from app.models.profile import Photo, Profile
        from app.services.ranking import calculate_relevancy_score

        def score(photos):
            profile = Profile(display_name="P", city="Miami")
            profile.photos = photos
            return calculate_relevancy_score(
                profile, sugar_user["user"], None, None, 0, None, None
            )

        held = score([Photo(url="/a.jpg", is_flagged=True)])
        visible = score([Photo(url="/b.jpg", is_flagged=False)])
        assert held < visible


@pytest.fixture
def as_admin(monkeypatch, sugar_user):
    """Admin access is an email allowlist, not a column."""
    monkeypatch.setattr(
        "app.routers.admin.ADMIN_EMAILS", {sugar_user["user"].email}
    )
    return sugar_user


class TestModeratorRemoval:
    """Removing a photo has to remove the file, not just the row — S3 serves
    URLs directly and serve_photo reads by filename without a database check."""

    @pytest.mark.asyncio
    async def test_remove_deletes_the_stored_file(self, client, db, as_admin, monkeypatch):
        from app.models.profile import Photo
        from app.services import storage as storage_module
        from tests.conftest import auth_header

        deleted: list[str] = []

        async def fake_delete(filename):
            deleted.append(filename)

        monkeypatch.setattr(storage_module.storage, "delete", fake_delete)

        photo = Photo(
            profile_id=as_admin["profile"].id, url="/uploads/held.jpg",
            is_flagged=True, moderation_status="flagged", is_primary=True,
        )
        db.add(photo)
        await db.commit()
        await db.refresh(photo)

        r = await client.post(
            f"/api/admin/photos/{photo.id}/review",
            params={"action": "remove"},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 200, r.text
        assert deleted == ["held.jpg"]

    @pytest.mark.asyncio
    async def test_removing_the_primary_promotes_another_photo(
        self, client, db, as_admin, monkeypatch
    ):
        """Discovery only ever shows the primary photo — leaving a profile
        without one would drop the member out of the feed entirely."""
        from app.models.profile import Photo
        from app.services import storage as storage_module
        from tests.conftest import auth_header

        async def fake_delete(filename):
            return None

        monkeypatch.setattr(storage_module.storage, "delete", fake_delete)

        bad = Photo(
            profile_id=as_admin["profile"].id, url="/uploads/bad.jpg",
            is_primary=True, order=0, is_flagged=True, moderation_status="flagged",
        )
        good = Photo(
            profile_id=as_admin["profile"].id, url="/uploads/good.jpg",
            is_primary=False, order=1,
        )
        db.add_all([bad, good])
        await db.commit()
        await db.refresh(bad)
        await db.refresh(good)

        r = await client.post(
            f"/api/admin/photos/{bad.id}/review",
            params={"action": "remove"},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 200, r.text

        await db.refresh(good)
        assert good.is_primary is True

    @pytest.mark.asyncio
    async def test_approve_clears_the_flag_and_keeps_the_photo(
        self, client, db, as_admin
    ):
        from app.models.profile import Photo
        from tests.conftest import auth_header

        photo = Photo(
            profile_id=as_admin["profile"].id, url="/uploads/ok.jpg",
            is_flagged=True, flag_reason="Suggestive (60%)", moderation_status="flagged",
        )
        db.add(photo)
        await db.commit()
        await db.refresh(photo)

        r = await client.post(
            f"/api/admin/photos/{photo.id}/review",
            params={"action": "approve"},
            headers=auth_header(as_admin["token"]),
        )
        assert r.status_code == 200, r.text

        await db.refresh(photo)
        assert photo.is_flagged is False
        assert photo.is_visible is True
        assert photo.moderation_status == "passed"
