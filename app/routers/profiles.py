import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.models.profile import Profile
from app.models.verification import VerificationRequest, VerificationType, VerificationStatus
from app.schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse
from app.services.content_filter import scan_text
from app.services.audit import log_action
from app.services.geocoder import geocode_city
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def calculate_age(born: date) -> int:
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def profile_to_response(profile: Profile, user: User | None = None) -> ProfileResponse:
    from datetime import datetime, timedelta
    is_online = False
    last_active = None
    if user and user.last_seen:
        is_online = (datetime.utcnow() - user.last_seen) < timedelta(minutes=5)
        last_active = user.last_seen.isoformat()

    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        user_type=user.user_type if user else None,
        is_online=is_online,
        last_active=last_active,
        display_name=profile.display_name,
        bio=profile.bio,
        headline=profile.headline,
        date_of_birth=profile.date_of_birth,
        age=calculate_age(profile.date_of_birth),
        gender=profile.gender,
        seeking_gender=profile.seeking_gender,
        sexual_orientation=profile.sexual_orientation,
        pronouns=profile.pronouns,
        city=profile.city,
        state=profile.state,
        country=profile.country,
        height_cm=profile.height_cm,
        body_type=profile.body_type,
        ethnicity=profile.ethnicity,
        education=profile.education,
        occupation=profile.occupation,
        languages=profile.languages,
        income_range=profile.income_range,
        net_worth_range=profile.net_worth_range,
        lifestyle_expectation=profile.lifestyle_expectation,
        looking_for=profile.looking_for,
        offering=profile.offering,
        arrangement_types=profile.arrangement_types,
        interests=profile.interests,
        lifestyle_tags=profile.lifestyle_tags,
        relationship_status=profile.relationship_status,
        availability=profile.availability,
        drinking=profile.drinking,
        smoking=profile.smoking,
        has_children=profile.has_children,
        ideal_first_date=profile.ideal_first_date,
        net_worth=getattr(profile, "net_worth", None),
        show_up_traits=getattr(profile, "show_up_traits", None),
        plus_traits=getattr(profile, "plus_traits", None),
        generosity=getattr(profile, "generosity", None),
        is_photo_verified=profile.is_photo_verified,
        is_income_verified=profile.is_income_verified,
        is_seed=profile.is_seed,
        is_traveling=profile.is_traveling,
        travel_city=profile.travel_city if profile.is_traveling else None,
        photos=[p for p in profile.photos if not p.is_private],
        created_at=profile.created_at,
    )


@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: ProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.profile:
        raise HTTPException(status_code=400, detail="Profile already exists")

    age = calculate_age(data.date_of_birth)
    if age < 18:
        raise HTTPException(status_code=400, detail="Must be 18 or older")

    # Enforce type-appropriate fields
    profile_data = data.model_dump()
    if user.user_type == UserType.SUGAR:
        profile_data.pop("lifestyle_expectation", None)
    elif user.user_type == UserType.ATTRACTIVE:
        profile_data.pop("income_range", None)
        profile_data.pop("net_worth_range", None)

    profile = Profile(user_id=user.id, **profile_data)

    # Geocode city to lat/lon
    lat, lon = await geocode_city(data.city, data.state, data.country)
    if lat is not None:
        profile.latitude = lat
        profile.longitude = lon

    # Content scan for FOSTA/SESTA compliance
    text_to_scan = " ".join(filter(None, [data.bio, data.headline, data.looking_for, data.offering]))
    flagged, matched = scan_text(text_to_scan)
    if flagged:
        profile.is_flagged = True
        profile.flag_reason = matched

    db.add(profile)
    await db.flush()

    if flagged:
        await log_action(db, actor_type="system", action="flag_profile", resource_type="profile", resource_id=profile.id, details={"matched_term": matched})

    # Grant new member boost to attractive members
    if user.user_type == UserType.ATTRACTIVE:
        from app.routers.boosts import grant_new_member_boost
        await grant_new_member_boost(profile.id, db)

    # Track profile creation in funnel
    from app.models.funnel import FunnelEvent
    db.add(FunnelEvent(user_id=user.id, user_type=user.user_type.value, event="profile_created"))

    await db.commit()
    await db.refresh(profile)

    # Notify admin with full profile details
    try:
        from app.services.email import send_admin_new_user
        from datetime import date
        age = ""
        if profile.date_of_birth:
            today = date.today()
            age = str(today.year - profile.date_of_birth.year - ((today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)))
        send_admin_new_user(
            email=user.email,
            user_type=user.user_type.value,
            city=profile.city or "",
            display_name=profile.display_name or "",
            gender=profile.gender.value if profile.gender else "",
            age=age,
        )
    except Exception:
        pass

    # Auto-like from seed profiles — drives immediate engagement
    try:
        from app.services.engagement import auto_like_new_profile
        await auto_like_new_profile(profile.id, user.id, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ENGAGEMENT] Auto-like failed: {e}")
    return profile_to_response(profile, user)


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(user: User = Depends(get_current_user)):
    if not user.profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile_to_response(user.profile, user)


@router.patch("/me", response_model=ProfileResponse)
@limiter.limit("10/minute")
async def update_my_profile(
    request: Request,
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user.profile, field, value)

    # Re-geocode if city, state, or country changed
    if "city" in update_data or "state" in update_data or "country" in update_data:
        lat, lon = await geocode_city(user.profile.city, user.profile.state, user.profile.country)
        if lat is not None:
            user.profile.latitude = lat
            user.profile.longitude = lon

    # Re-scan profile content after update
    p = user.profile
    text_to_scan = " ".join(filter(None, [p.bio, p.headline, p.looking_for, p.offering]))
    flagged, matched = scan_text(text_to_scan)
    p.is_flagged = flagged
    p.flag_reason = matched if flagged else None
    if flagged:
        await log_action(db, actor_type="system", action="flag_profile", resource_type="profile", resource_id=p.id, details={"matched_term": matched})

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Failed to update profile. Please try again.")
    await db.refresh(user.profile)
    return profile_to_response(user.profile, user)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile or profile.is_hidden:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_user_result = await db.execute(select(User).where(User.id == profile.user_id))
    profile_user = profile_user_result.scalar_one_or_none()

    # Track profile view + notify paying SDs (skip own profile views)
    if user.profile and profile.user_id != user.id:
        viewer_city = user.profile.city or ""
        background_tasks.add_task(
            _handle_profile_view,
            viewed_profile_id=profile.id,
            viewed_user_id=profile.user_id,
            viewed_display_name=profile.display_name,
            viewed_user_type=profile_user.user_type.value if profile_user else None,
            viewed_user_email=profile_user.email if profile_user else None,
            viewer_user_id=user.id,
            viewer_user_type=user.user_type.value,
            viewer_city=viewer_city,
        )

    return profile_to_response(profile, profile_user)


async def _handle_profile_view(
    *,
    viewed_profile_id: int,
    viewed_user_id: int,
    viewed_display_name: str,
    viewed_user_type: str | None,
    viewed_user_email: str | None,
    viewer_user_id: int,
    viewer_user_type: str,
    viewer_city: str,
):
    """Log profile view as FunnelEvent and email paying SDs (max 1/hour).

    Uses its own DB session since FastAPI background tasks run after the
    request session is closed.
    """
    from app.database import async_session
    from app.models.funnel import FunnelEvent

    async with async_session() as db:
        try:
            # Log funnel event
            db.add(FunnelEvent(
                user_id=viewer_user_id,
                user_type=viewer_user_type,
                event="profile_viewed",
                metadata_={"viewed_profile_id": viewed_profile_id, "viewer_city": viewer_city},
            ))
            await db.commit()
        except Exception as e:
            logger.error(f"[PROFILE_VIEW] Failed to log funnel event: {e}")

        # Only notify paying sugar daddies
        if viewed_user_type != UserType.SUGAR.value or not viewed_user_email:
            return

        try:
            from app.models.subscription import Subscription, SubscriptionTier

            sub_r = await db.execute(
                select(Subscription).where(
                    Subscription.user_id == viewed_user_id,
                    Subscription.is_active == True,
                    Subscription.tier.in_([SubscriptionTier.PLUS, SubscriptionTier.PLUS_PLUS]),
                )
            )
            if not sub_r.scalar_one_or_none():
                return  # Not a paying subscriber

            # Throttle: skip if we already emailed about a view in the last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_r = await db.execute(
                select(FunnelEvent.id).where(
                    FunnelEvent.event == "profile_view_emailed",
                    FunnelEvent.user_id == viewed_user_id,
                    FunnelEvent.created_at >= one_hour_ago,
                ).limit(1)
            )
            if recent_r.scalar_one_or_none():
                return  # Already emailed recently

            # Send notification
            from app.services.email import send_profile_viewed
            send_profile_viewed(
                to=viewed_user_email,
                display_name=viewed_display_name,
                viewer_city=viewer_city,
            )

            # Mark that we emailed so we can throttle
            db.add(FunnelEvent(
                user_id=viewed_user_id,
                user_type=viewed_user_type,
                event="profile_view_emailed",
                metadata_={"viewer_city": viewer_city},
            ))
            await db.commit()
        except Exception as e:
            logger.error(f"[PROFILE_VIEW] Failed to send notification: {e}")


# ─── Verification Submission (any authenticated user) ───

@router.post("/verify/{type}")
async def submit_verification(
    type: VerificationType,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a verification request. Type: 'photo' or 'income'."""
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    # Check for existing pending request
    existing = await db.execute(
        select(VerificationRequest).where(
            VerificationRequest.user_id == user.id,
            VerificationRequest.type == type,
            VerificationRequest.status == VerificationStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a pending verification request for this type")

    # Check if already verified
    if type == VerificationType.PHOTO and user.profile.is_photo_verified:
        raise HTTPException(status_code=400, detail="Your photos are already verified")
    if type == VerificationType.INCOME and user.profile.is_income_verified:
        raise HTTPException(status_code=400, detail="Your income is already verified")

    req = VerificationRequest(user_id=user.id, type=type)
    db.add(req)
    await db.commit()

    # Notify admin
    try:
        from app.services.email import send_admin_new_user
        send_admin_new_user(user.email, f"verification_{type.value}")
    except Exception:
        pass

    return {"submitted": True, "type": type.value}


@router.get("/verify/status")
async def get_verification_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's verification status."""
    if not user.profile:
        return {"photo_verified": False, "income_verified": False, "pending_photo": False, "pending_income": False}

    pending_photo = await db.execute(
        select(VerificationRequest).where(
            VerificationRequest.user_id == user.id,
            VerificationRequest.type == VerificationType.PHOTO,
            VerificationRequest.status == VerificationStatus.PENDING,
        )
    )
    pending_income = await db.execute(
        select(VerificationRequest).where(
            VerificationRequest.user_id == user.id,
            VerificationRequest.type == VerificationType.INCOME,
            VerificationRequest.status == VerificationStatus.PENDING,
        )
    )

    return {
        "photo_verified": user.profile.is_photo_verified,
        "income_verified": user.profile.is_income_verified,
        "pending_photo": pending_photo.scalar_one_or_none() is not None,
        "pending_income": pending_income.scalar_one_or_none() is not None,
    }


# ─── Travel Mode (simple set/clear) ───

class TravelCityRequest(BaseModel):
    city: str | None = Field(None, max_length=100)


@router.post("/travel")
async def set_travel_city(
    data: TravelCityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set or clear travel city. Send {"city": "Miami"} to set, {"city": null} to clear."""
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    if data.city:
        # Geocode the travel city
        lat, lon = await geocode_city(data.city, None, None)
        user.profile.is_traveling = True
        user.profile.travel_city = data.city
        user.profile.travel_latitude = lat
        user.profile.travel_longitude = lon
    else:
        user.profile.is_traveling = False
        user.profile.travel_city = None
        user.profile.travel_latitude = None
        user.profile.travel_longitude = None
        user.profile.travel_until = None

    await db.commit()
    await db.refresh(user.profile)

    return {
        "is_traveling": user.profile.is_traveling,
        "travel_city": user.profile.travel_city,
        "city": user.profile.city,
    }
