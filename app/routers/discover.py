"""Discover endpoint with relevancy-ranked results."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.models.profile import (
    Profile, Gender, IncomeRange, Education, BodyType, LifestyleExpectation,
)
from app.models.match import Like
from app.models.safety import Block
from app.models.subscription import Subscription, SubscriptionTier
from app.models.boost import Boost
from app.routers.profiles import profile_to_response
from app.routers.location import get_active_location, haversine_miles
from app.services.ranking import calculate_relevancy_score

router = APIRouter(prefix="/api/discover", tags=["discover"])

INCOME_ORDER = [
    IncomeRange.UNDER_100K, IncomeRange.R100K_250K, IncomeRange.R250K_500K,
    IncomeRange.R500K_1M, IncomeRange.R1M_5M, IncomeRange.R5M_10M, IncomeRange.OVER_10M,
]


def _safe_dob(year: int, month: int, day: int) -> date:
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, max_day))


@router.get("/", response_model=list)
async def discover_profiles(
    min_age: int | None = Query(None, ge=18),
    max_age: int | None = Query(None, le=100),
    gender: Gender | None = None,
    user_type: UserType | None = None,
    city: str | None = None,
    max_distance: int | None = Query(None, ge=1, le=500),
    education: Education | None = None,
    income_range: IncomeRange | None = None,
    body_type: BodyType | None = None,
    lifestyle_expectation: LifestyleExpectation | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Profile, User)
        .join(User, Profile.user_id == User.id)
        .where(Profile.is_active == True, Profile.is_hidden == False, Profile.user_id != user.id)
    )

    # Exclude liked and blocked
    if user.profile:
        liked_subq = select(Like.to_profile_id).where(Like.from_profile_id == user.profile.id)
        query = query.where(Profile.id.notin_(liked_subq))

        blocked_subq = select(Block.blocked_profile_id).where(Block.blocker_profile_id == user.profile.id)
        blocked_by_subq = select(Block.blocker_profile_id).where(Block.blocked_profile_id == user.profile.id)
        query = query.where(Profile.id.notin_(blocked_subq))
        query = query.where(Profile.id.notin_(blocked_by_subq))

    # Cross-type only: sugar members see attractive, attractive see sugar
    if user.user_type == UserType.SUGAR:
        query = query.where(User.user_type == UserType.ATTRACTIVE)
    elif user.user_type == UserType.ATTRACTIVE:
        query = query.where(User.user_type == UserType.SUGAR)

    # Mutual gender preference
    if user.profile and user.profile.seeking_gender:
        query = query.where(Profile.gender == user.profile.seeking_gender)
    if user.profile and user.profile.gender:
        query = query.where(
            (Profile.seeking_gender == None) | (Profile.seeking_gender == user.profile.gender)
        )

    # Sexual orientation filtering — hide profiles that explicitly wouldn't match
    if user.profile and user.profile.sexual_orientation:
        from app.models.profile import SexualOrientation
        orientation = user.profile.sexual_orientation
        # If user is gay/lesbian, only show same-gender profiles
        if orientation == SexualOrientation.GAY or orientation == SexualOrientation.LESBIAN:
            query = query.where(Profile.gender == user.profile.gender)
        # If user is straight, only show opposite-gender profiles
        elif orientation == SexualOrientation.STRAIGHT:
            query = query.where(Profile.gender != user.profile.gender)
        # Bisexual/pansexual/queer/asexual/prefer_not_to_say — show all genders (no filter)

    # Also hide profiles whose orientation excludes the current user
    if user.profile and user.profile.gender:
        from app.models.profile import SexualOrientation, Gender
        user_gender = user.profile.gender
        # Don't show gay/lesbian profiles to opposite-gender users
        if user_gender == Gender.MALE:
            query = query.where(
                (Profile.sexual_orientation == None) |
                (~Profile.sexual_orientation.in_([SexualOrientation.LESBIAN]))
            )
        elif user_gender == Gender.FEMALE:
            query = query.where(
                (Profile.sexual_orientation == None) |
                (~Profile.sexual_orientation.in_([SexualOrientation.GAY]))
            )

    # Filters
    if gender:
        query = query.where(Profile.gender == gender)
    if user_type:
        query = query.where(User.user_type == user_type)
    if city:
        query = query.where(
            (func.lower(Profile.city) == city.lower()) |
            ((Profile.is_traveling == True) & (func.lower(Profile.travel_city) == city.lower()))
        )
    if education:
        query = query.where(Profile.education == education)
    if body_type:
        query = query.where(Profile.body_type == body_type)
    if lifestyle_expectation:
        query = query.where(Profile.lifestyle_expectation == lifestyle_expectation)
    if income_range:
        min_idx = INCOME_ORDER.index(income_range)
        query = query.where(Profile.income_range.in_(INCOME_ORDER[min_idx:]))

    today = date.today()
    if min_age:
        query = query.where(Profile.date_of_birth <= _safe_dob(today.year - min_age, today.month, today.day))
    if max_age:
        query = query.where(Profile.date_of_birth >= _safe_dob(today.year - max_age - 1, today.month, today.day))

    # Fetch more than page_size so we can rank and then paginate
    query = query.limit(page_size * 3)
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return []

    # Get my location for distance scoring
    my_lat, my_lon = None, None
    if user.profile:
        _, my_lat, my_lon = get_active_location(user.profile)

    # Batch load subscriptions and boosts for all profiles
    profile_ids = [p.id for p, u in rows]
    user_ids = [u.id for p, u in rows]

    subs_result = await db.execute(select(Subscription).where(Subscription.user_id.in_(user_ids)))
    subs_map = {s.user_id: s for s in subs_result.scalars().all()}

    now = datetime.utcnow()
    boosts_result = await db.execute(
        select(Boost).where(
            Boost.profile_id.in_(profile_ids),
            Boost.is_active == True,
            Boost.expires_at > now,
        )
    )
    boosts_map = {b.profile_id: b for b in boosts_result.scalars().all()}

    # Batch load like counts
    likes_result = await db.execute(
        select(Like.to_profile_id, func.count(Like.id))
        .where(Like.to_profile_id.in_(profile_ids))
        .group_by(Like.to_profile_id)
    )
    likes_map = dict(likes_result.all())

    # Score and rank
    scored_profiles = []
    for profile, u in rows:
        score = calculate_relevancy_score(
            profile=profile,
            profile_user=u,
            subscription=subs_map.get(u.id),
            active_boost=boosts_map.get(profile.id),
            likes_received=likes_map.get(profile.id, 0),
            my_lat=my_lat,
            my_lon=my_lon,
        )
        scored_profiles.append((profile, u, score))

    # Sort by score descending
    scored_profiles.sort(key=lambda x: x[2], reverse=True)

    # Paginate after ranking
    start = (page - 1) * page_size
    page_results = scored_profiles[start:start + page_size]

    # Determine "new" threshold (joined within 7 days)
    new_threshold = datetime.utcnow() - timedelta(days=7)
    # Popular threshold: profiles with 5+ likes
    popular_threshold = 5

    # Distance filter + tags
    responses = []
    for profile, u, score in page_results:
        resp = profile_to_response(profile, u)

        if my_lat and my_lon:
            _, p_lat, p_lon = get_active_location(profile)
            if p_lat and p_lon:
                dist = haversine_miles(my_lat, my_lon, p_lat, p_lon)
                if max_distance and dist > max_distance:
                    continue
                resp.distance_miles = round(dist)

        # Add tags
        sub = subs_map.get(u.id)
        has_boost = profile.id in boosts_map
        is_premium_tier = sub and sub.tier in (SubscriptionTier.PLUS, SubscriptionTier.PLUS_PLUS) and sub.is_active
        is_new = profile.created_at >= new_threshold

        # Featured logic:
        # 1. Active boost or Diamond subscriber (paid)
        # 2. New user (first 7 days — auto-featured)
        # 3. Quality profile: photo verified + 3+ photos + bio filled + arrangement types set + active in last 7 days
        has_quality_profile = (
            profile.is_photo_verified
            and len(profile.photos) >= 3
            and profile.bio
            and profile.arrangement_types
            and u.last_seen and u.last_seen >= new_threshold
        )
        resp.is_featured = has_boost or is_premium_tier or is_new or has_quality_profile
        resp.is_new = is_new
        resp.is_popular = likes_map.get(profile.id, 0) >= popular_threshold
        if sub and sub.is_active:
            resp.subscription_tier = sub.tier.value

        responses.append(resp)

    return responses


@router.get("/preview")
async def preview_profiles(db: AsyncSession = Depends(get_db)):
    """Public endpoint — returns 8 random profiles for the homepage preview.
    No auth required. Returns minimal data, no full content."""
    import random

    result = await db.execute(
        select(Profile, User)
        .join(User, User.id == Profile.user_id)
        .where(
            Profile.is_active == True,
            Profile.is_hidden == False,
            Profile.is_seed == True,
        )
        .limit(40)
    )
    rows = result.all()

    if not rows:
        return []

    sampled = random.sample(list(rows), min(8, len(rows)))
    apiBase = "/api/photos/file/"

    previews = []
    for profile, user in sampled:
        photo_url = None
        if profile.photos:
            primary = next((p for p in profile.photos if p.is_primary and not p.is_private), None)
            if primary:
                photo_url = primary.url

        previews.append({
            "display_name": profile.display_name,
            "age": (date.today().year - profile.date_of_birth.year
                    - ((date.today().month, date.today().day) < (profile.date_of_birth.month, profile.date_of_birth.day))),
            "city": profile.city or "",
            "occupation": profile.occupation or "",
            "photo_url": photo_url,
            "is_verified": profile.is_photo_verified or profile.is_income_verified,
        })

    return previews
