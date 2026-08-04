"""Referral dashboard.

The dashboard 500'd on every request for months because the Premium/Diamond
to Plus/Plus+ rename missed two dictionary keys. Nothing caught it: the keys
are read at request time, not at import, and no test exercised the endpoint.
These do.
"""
import pytest

from app.routers.referrals import COMMISSION_TIERS, get_commission_tier
from tests.conftest import auth_header


class TestCommissionTiers:
    """The response builder indexes these by name, so the shape is a contract."""

    def test_every_tier_has_the_keys_the_response_reads(self):
        for tier in COMMISSION_TIERS:
            assert "plus" in tier, f"{tier['name']} missing 'plus'"
            assert "plus_plus" in tier, f"{tier['name']} missing 'plus_plus'"
            assert "name" in tier and "min_paying" in tier

    def test_no_legacy_tier_names_remain(self):
        """'premium' and 'diamond' are the old names. Their absence here is
        what the endpoint depends on being true in the other direction."""
        for tier in COMMISSION_TIERS:
            assert "premium" not in tier
            assert "diamond" not in tier

    def test_tier_selection_by_referral_count(self):
        assert get_commission_tier(0)["name"] == "Starter"
        assert get_commission_tier(24)["name"] == "Starter"
        assert get_commission_tier(25)["name"] == "Silver"
        assert get_commission_tier(150)["name"] == "Gold"
        assert get_commission_tier(10_000)["name"] == "Platinum"

    def test_rates_increase_with_tier(self):
        for lower, higher in zip(COMMISSION_TIERS, COMMISSION_TIERS[1:]):
            assert higher["plus"] > lower["plus"]
            assert higher["plus_plus"] > lower["plus_plus"]


class TestDashboardEndpoint:
    @pytest.mark.asyncio
    async def test_dashboard_returns_200(self, client, sugar_user):
        r = await client.get(
            "/api/referrals/dashboard", headers=auth_header(sugar_user["token"])
        )
        assert r.status_code == 200, r.text

    @pytest.mark.asyncio
    async def test_dashboard_reports_rates_for_both_tiers(self, client, sugar_user):
        r = await client.get(
            "/api/referrals/dashboard", headers=auth_header(sugar_user["token"])
        )
        rates = r.json()["rates"]
        assert "plus" in rates and "plus_plus" in rates
        # The KeyError produced a 500; a formatting slip would produce "$None".
        assert "None" not in rates["plus"]
        assert "None" not in rates["plus_plus"]

    @pytest.mark.asyncio
    async def test_new_member_starts_on_the_first_tier(self, client, sugar_user):
        r = await client.get(
            "/api/referrals/dashboard", headers=auth_header(sugar_user["token"])
        )
        body = r.json()
        assert body["current_tier"] == "Starter"
        assert body["total_referrals"] == 0
        assert body["unpaid_balance"] == 0

    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self, client):
        r = await client.get("/api/referrals/dashboard")
        assert r.status_code in (401, 403)
