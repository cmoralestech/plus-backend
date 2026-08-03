"""Tests for profile ranking/scoring in discover feed."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from app.services.ranking import calculate_relevancy_score
from app.models.subscription import Subscription, SubscriptionTier


def _make_profile(**kwargs):
    p = MagicMock()
    p.photos = kwargs.get("photos", [1, 2, 3])  # mock 3 photos
    p.is_photo_verified = kwargs.get("photo_verified", False)
    p.is_income_verified = kwargs.get("income_verified", False)
    p.bio = kwargs.get("bio", "Test bio")
    p.headline = kwargs.get("headline", "Test headline")
    p.looking_for = kwargs.get("looking_for", "Someone")
    p.offering = kwargs.get("offering", "Good times")
    p.occupation = kwargs.get("occupation", "CEO")
    p.interests = kwargs.get("interests", ["travel"])
    p.arrangement_types = kwargs.get("arrangement_types", ["dating"])
    p.ideal_first_date = kwargs.get("ideal_first_date", "Dinner")
    p.latitude = kwargs.get("lat", 25.76)
    p.longitude = kwargs.get("lon", -80.19)
    p.is_traveling = False
    p.travel_latitude = None
    p.travel_longitude = None
    return p


def _make_user(**kwargs):
    u = MagicMock()
    u.created_at = kwargs.get("created_at", datetime.utcnow())
    u.last_seen = kwargs.get("last_seen", datetime.utcnow())
    return u


class TestRankingBasics:
    def test_returns_numeric_score(self):
        score = calculate_relevancy_score(
            _make_profile(), _make_user(), None, None, 0, None, None
        )
        assert isinstance(score, float)
        assert score >= 0

    def test_complete_profile_scores_higher(self):
        complete = _make_profile(bio="Full bio", headline="Great headline")
        empty = _make_profile(bio=None, headline=None, looking_for=None, offering=None,
                              occupation=None, interests=None, arrangement_types=None, ideal_first_date=None)

        score_complete = calculate_relevancy_score(complete, _make_user(), None, None, 0, None, None)
        score_empty = calculate_relevancy_score(empty, _make_user(), None, None, 0, None, None)
        assert score_complete > score_empty


class TestVerificationBoost:
    def test_photo_verified_scores_higher(self):
        verified = _make_profile(photo_verified=True)
        unverified = _make_profile(photo_verified=False)
        u = _make_user()

        score_v = calculate_relevancy_score(verified, u, None, None, 0, None, None)
        score_u = calculate_relevancy_score(unverified, u, None, None, 0, None, None)
        assert score_v > score_u

    def test_income_verified_scores_higher(self):
        verified = _make_profile(income_verified=True)
        unverified = _make_profile(income_verified=False)
        u = _make_user()

        score_v = calculate_relevancy_score(verified, u, None, None, 0, None, None)
        score_u = calculate_relevancy_score(unverified, u, None, None, 0, None, None)
        assert score_v > score_u


class TestSubscriptionBoost:
    def test_plus_plus_scores_higher_than_free(self):
        p = _make_profile()
        u = _make_user()
        diamond = MagicMock(tier=SubscriptionTier.PLUS_PLUS, is_active=True)

        score_plus_plus = calculate_relevancy_score(p, u, diamond, None, 0, None, None)
        score_free = calculate_relevancy_score(p, u, None, None, 0, None, None)
        assert score_plus_plus > score_free

    def test_plus_scores_higher_than_free(self):
        p = _make_profile()
        u = _make_user()
        premium = MagicMock(tier=SubscriptionTier.PLUS, is_active=True)

        score_plus = calculate_relevancy_score(p, u, premium, None, 0, None, None)
        score_free = calculate_relevancy_score(p, u, None, None, 0, None, None)
        assert score_plus > score_free

    def test_plus_plus_scores_higher_than_plus(self):
        p = _make_profile()
        u = _make_user()
        diamond = MagicMock(tier=SubscriptionTier.PLUS_PLUS, is_active=True)
        premium = MagicMock(tier=SubscriptionTier.PLUS, is_active=True)

        score_plus_plus = calculate_relevancy_score(p, u, diamond, None, 0, None, None)
        score_plus = calculate_relevancy_score(p, u, premium, None, 0, None, None)
        assert score_plus_plus > score_plus


class TestNewMemberBoost:
    def test_new_member_scores_higher(self):
        p = _make_profile()
        new_user = _make_user(created_at=datetime.utcnow() - timedelta(days=1))
        old_user = _make_user(created_at=datetime.utcnow() - timedelta(days=30))

        score_new = calculate_relevancy_score(p, new_user, None, None, 0, None, None)
        score_old = calculate_relevancy_score(p, old_user, None, None, 0, None, None)
        assert score_new > score_old

    def test_new_member_boost_decays(self):
        p = _make_profile()
        day1 = _make_user(created_at=datetime.utcnow() - timedelta(days=1))
        day6 = _make_user(created_at=datetime.utcnow() - timedelta(days=6))

        score_1 = calculate_relevancy_score(p, day1, None, None, 0, None, None)
        score_6 = calculate_relevancy_score(p, day6, None, None, 0, None, None)
        assert score_1 > score_6

    def test_no_boost_after_7_days(self):
        p = _make_profile()
        day8 = _make_user(created_at=datetime.utcnow() - timedelta(days=8))
        day30 = _make_user(created_at=datetime.utcnow() - timedelta(days=30))

        score_8 = calculate_relevancy_score(p, day8, None, None, 0, None, None)
        score_30 = calculate_relevancy_score(p, day30, None, None, 0, None, None)
        # After 7 days, both get 0 new member boost — scores differ only by activity
        assert abs(score_8 - score_30) < 50


class TestActivityBoost:
    def test_online_now_highest(self):
        p = _make_profile()
        online = _make_user(last_seen=datetime.utcnow() - timedelta(minutes=1))
        yesterday = _make_user(last_seen=datetime.utcnow() - timedelta(hours=20))

        score_on = calculate_relevancy_score(p, online, None, None, 0, None, None)
        score_off = calculate_relevancy_score(p, yesterday, None, None, 0, None, None)
        assert score_on > score_off

    def test_inactive_gets_no_boost(self):
        p = _make_profile()
        active = _make_user(last_seen=datetime.utcnow())
        inactive = _make_user(last_seen=datetime.utcnow() - timedelta(days=10))

        score_a = calculate_relevancy_score(p, active, None, None, 0, None, None)
        score_i = calculate_relevancy_score(p, inactive, None, None, 0, None, None)
        assert score_a > score_i


class TestBoostOverride:
    def test_active_boost_highest_priority(self):
        p = _make_profile()
        u = _make_user()
        boost = MagicMock(is_active=True, expires_at=datetime.utcnow() + timedelta(hours=1))

        score_boosted = calculate_relevancy_score(p, u, None, boost, 0, None, None)
        score_normal = calculate_relevancy_score(p, u, None, None, 0, None, None)
        assert score_boosted > score_normal
        assert score_boosted - score_normal >= 1000  # boost is worth 1000 points
