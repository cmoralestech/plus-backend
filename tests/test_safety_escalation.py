"""Report escalation behaviour.

Trafficking and underage reports are the two categories where waiting for a
threshold is not acceptable, so they act on the first report and pull the
profile out of discovery while a human reviews it. Everything else accumulates.
These are compliance-visible guarantees — we tell payment processors and app
stores that this is what happens.
"""
import pytest
from sqlalchemy import select

from app.models.profile import Profile
from app.models.safety import Report
from tests.conftest import auth_header


async def _report(client, reporter, target_profile_id, reason, **kw):
    return await client.post(
        f"/api/safety/report/{target_profile_id}",
        params={"reason": reason, **kw},
        headers=auth_header(reporter["token"]),
    )


class TestImmediateEscalation:
    """First report is enough for these two categories."""

    @pytest.mark.asyncio
    async def test_trafficking_report_flags_and_hides_immediately(
        self, client, db, sugar_user, attractive_user
    ):
        target = attractive_user["profile"]
        r = await _report(client, sugar_user, target.id, "human_trafficking")
        assert r.status_code == 201

        await db.refresh(target)
        assert target.is_flagged is True
        assert target.flag_reason == "Human trafficking report"
        assert target.is_hidden is True

    @pytest.mark.asyncio
    async def test_underage_report_flags_and_hides_immediately(
        self, client, db, sugar_user, attractive_user
    ):
        target = attractive_user["profile"]
        r = await _report(client, sugar_user, target.id, "underage")
        assert r.status_code == 201

        await db.refresh(target)
        assert target.is_flagged is True
        assert target.flag_reason == "Underage report"
        assert target.is_hidden is True

    @pytest.mark.asyncio
    async def test_escalation_does_not_deactivate_on_one_report(
        self, client, db, sugar_user, attractive_user
    ):
        """Hidden pending review, not suspended — a moderator decides that."""
        target = attractive_user["profile"]
        await _report(client, sugar_user, target.id, "underage")

        await db.refresh(target)
        assert target.is_active is True


class TestThresholdEscalation:
    """Ordinary categories accumulate rather than acting on one report."""

    @pytest.mark.asyncio
    async def test_single_ordinary_report_does_not_flag(
        self, client, db, sugar_user, attractive_user
    ):
        target = attractive_user["profile"]
        r = await _report(client, sugar_user, target.id, "harassment")
        assert r.status_code == 201

        await db.refresh(target)
        assert target.is_flagged is False
        assert target.is_hidden is False

    @pytest.mark.asyncio
    async def test_third_report_flags_for_review(
        self, client, db, sugar_user, attractive_user
    ):
        target = attractive_user["profile"]
        # Two pre-existing reports from other members, then one through the API.
        db.add_all([
            Report(
                reporter_profile_id=sugar_user["profile"].id,
                reported_profile_id=target.id,
                reason="harassment",
            )
            for _ in range(2)
        ])
        await db.commit()

        await _report(client, sugar_user, target.id, "harassment")

        await db.refresh(target)
        assert target.is_flagged is True
        assert "3 reports" in target.flag_reason

    @pytest.mark.asyncio
    async def test_fifth_report_suspends(
        self, client, db, sugar_user, attractive_user
    ):
        target = attractive_user["profile"]
        db.add_all([
            Report(
                reporter_profile_id=sugar_user["profile"].id,
                reported_profile_id=target.id,
                reason="scam",
            )
            for _ in range(4)
        ])
        await db.commit()

        await _report(client, sugar_user, target.id, "scam")

        await db.refresh(target)
        assert target.is_active is False
        assert target.is_hidden is True


class TestReportValidity:
    @pytest.mark.asyncio
    async def test_cannot_report_self(self, client, sugar_user):
        r = await _report(
            client, sugar_user, sugar_user["profile"].id, "harassment"
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_unknown_profile_is_404(self, client, sugar_user):
        r = await _report(client, sugar_user, 999999, "harassment")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_report_is_persisted_with_reason(
        self, client, db, sugar_user, attractive_user
    ):
        target = attractive_user["profile"]
        await _report(
            client, sugar_user, target.id, "scam", details="asked for gift cards"
        )

        row = (
            await db.execute(
                select(Report).where(Report.reported_profile_id == target.id)
            )
        ).scalars().first()
        assert row is not None
        assert row.details == "asked for gift cards"
