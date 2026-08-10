"""Referrals: sharing a link, and no longer promising money for it.

The dashboard used to advertise a tiered commission — "$10/month per referral",
Starter through Platinum, a running balance and a $50 minimum payout. None of it
was ever real: no code has ever written a ReferralEarning row, so the balance was
always zero and always would have been. A live page was making a financial
promise the system could not keep.

Referring still exists; earning does not. These tests hold that line, because
the wording is the kind of thing that creeps back into a marketing page.
"""
import pytest

from tests.conftest import auth_header

# Every key the dashboard used to return that implied payment.
MONEY_KEYS = {
    "monthly_earnings",
    "total_earned",
    "unpaid_balance",
    "minimum_payout",
    "current_tier",
    "next_tier",
    "next_tier_requires",
    "commission_tiers",
    "rates",
}


class TestNoEarningsPromised:
    @pytest.mark.asyncio
    async def test_dashboard_makes_no_financial_claim(self, client, sugar_user):
        r = await client.get(
            "/api/referrals/dashboard", headers=auth_header(sugar_user["token"])
        )
        assert r.status_code == 200, r.text

        leaked = MONEY_KEYS & set(r.json())
        assert not leaked, f"the dashboard is promising money again: {sorted(leaked)}"

    @pytest.mark.asyncio
    async def test_the_commission_table_is_gone_from_the_module(self):
        """Removed rather than left unused: dead scaffolding for a payment scheme
        is exactly what gets rewired back into a response by accident."""
        import app.routers.referrals as referrals

        assert not hasattr(referrals, "COMMISSION_TIERS")
        assert not hasattr(referrals, "get_commission_tier")


class TestDashboardEndpoint:
    @pytest.mark.asyncio
    async def test_dashboard_returns_200(self, client, sugar_user):
        """It 500'd on every request for months — the Premium/Diamond to
        Plus/Plus+ rename missed two dictionary keys, read at request time
        rather than at import, and no test exercised the endpoint."""
        r = await client.get(
            "/api/referrals/dashboard", headers=auth_header(sugar_user["token"])
        )
        assert r.status_code == 200, r.text

    @pytest.mark.asyncio
    async def test_it_still_reports_what_sharing_achieved(self, client, sugar_user):
        r = await client.get(
            "/api/referrals/dashboard", headers=auth_header(sugar_user["token"])
        )
        body = r.json()
        assert body["total_referrals"] == 0
        assert body["clicks"] == 0
        assert "referral_link" in body

    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self, client):
        r = await client.get("/api/referrals/dashboard")
        assert r.status_code in (401, 403)
