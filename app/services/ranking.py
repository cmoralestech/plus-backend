"""Profile relevancy scoring engine for discover feed."""
from datetime import datetime, timedelta

from app.models.user import User
from app.models.profile import Profile
from app.models.subscription import Subscription, SubscriptionTier
from app.models.boost import Boost


def calculate_relevancy_score(
    profile: Profile,
    profile_user: User,
    subscription: Subscription | None,
    active_boost: Boost | None,
    likes_received: int,
    my_lat: float | None,
    my_lon: float | None,
) -> float:
    """Calculate a relevancy score for a profile. Higher = shown first."""
    score = 0.0
    now = datetime.utcnow()

    # === Boost (highest priority) ===
    if active_boost and active_boost.is_active and active_boost.expires_at > now:
        score += 1000

    # === New member boost (first 7 days for attractive members) ===
    if profile_user.created_at:
        days_old = (now - profile_user.created_at).days
        if days_old <= 7:
            score += max(0, 500 - (days_old * 50))  # Decays over the week: 500 → 150

    # === Subscription tier ===
    if subscription:
        if subscription.tier == SubscriptionTier.DIAMOND and subscription.is_active:
            score += 500  # Diamond users appear near the top of discover
        elif subscription.tier == SubscriptionTier.PREMIUM and subscription.is_active:
            score += 100

    # === Photos (heavily weighted — no-photo profiles sink to bottom) ===
    if profile.photos and len(profile.photos) > 0:
        score += 500
        if len(profile.photos) >= 3:
            score += 100  # Bonus for multiple photos
    else:
        score -= 300  # Penalty: push no-photo profiles to the end

    # === Verification ===
    if profile.is_photo_verified:
        score += 150
    if profile.is_income_verified:
        score += 100

    # === Profile completeness ===
    completeness_fields = [
        profile.bio, profile.headline, profile.looking_for, profile.offering,
        profile.occupation, profile.interests, profile.arrangement_types,
        profile.ideal_first_date,
    ]
    filled = sum(1 for f in completeness_fields if f)
    score += (filled / len(completeness_fields)) * 200

    # === Activity recency ===
    if profile_user.last_seen:
        since_seen = now - profile_user.last_seen
        if since_seen < timedelta(minutes=5):
            score += 300  # Online now
        elif since_seen < timedelta(hours=1):
            score += 250
        elif since_seen < timedelta(hours=24):
            score += 100
        elif since_seen < timedelta(days=3):
            score += 25
        # Inactive > 3 days: no bonus

    # === Distance ===
    if my_lat and my_lon and profile.latitude and profile.longitude:
        from app.routers.location import haversine_miles
        from app.routers.location import get_active_location
        _, p_lat, p_lon = get_active_location(profile)
        if p_lat and p_lon:
            dist = haversine_miles(my_lat, my_lon, p_lat, p_lon)
            if dist < 10:
                score += 200
            elif dist < 25:
                score += 150
            elif dist < 50:
                score += 100
            elif dist < 100:
                score += 75
            elif dist < 250:
                score += 25

    # === Social proof (likes received) ===
    score += min(likes_received * 2, 100)  # Cap at 100

    return score
