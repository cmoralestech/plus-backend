"""Admin endpoints for managing users, reports, and verifications."""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Request as FastAPIRequest
from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.profile import Profile
from app.models.safety import Report, Block
from app.models.audit import AuditLog
from app.services.audit import log_action
from app.models.match import Like, Match
from app.models.message import Message, Conversation
from app.models.verification import VerificationRequest, VerificationStatus, VerificationType

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Simple admin check — in production use proper role-based access
ADMIN_EMAILS = {"cmoralestech@gmail.com"}


async def require_admin(user: User = Depends(get_current_user)):
    if user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/stats")
async def get_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(select(func.count(User.id)))).scalar()
    profiles = (await db.execute(select(func.count(Profile.id)))).scalar()
    matches = (await db.execute(select(func.count(Match.id)))).scalar()
    messages = (await db.execute(select(func.count(Message.id)))).scalar()
    reports = (await db.execute(select(func.count(Report.id)))).scalar()
    pending_verifications = (await db.execute(
        select(func.count(VerificationRequest.id)).where(VerificationRequest.status == VerificationStatus.PENDING)
    )).scalar()

    flagged_messages = (await db.execute(
        select(func.count(Message.id)).where(Message.is_flagged == True, Message.reviewed_at == None)
    )).scalar()
    flagged_profiles = (await db.execute(
        select(func.count(Profile.id)).where(Profile.is_flagged == True, Profile.reviewed_at == None)
    )).scalar()

    return {
        "users": users,
        "profiles": profiles,
        "matches": matches,
        "messages": messages,
        "reports": reports,
        "pending_verifications": pending_verifications,
        "flagged_messages": flagged_messages,
        "flagged_profiles": flagged_profiles,
    }


@router.get("/stats/timeline")
async def get_stats_timeline(
    days: int = 30,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Daily signup counts for the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(User.created_at).label("day"),
            func.count(User.id).label("count"),
        )
        .where(User.created_at >= cutoff)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    )
    rows = result.all()
    return [{"date": str(r.day), "signups": r.count} for r in rows]


@router.get("/new-users")
async def get_new_users(
    days: int = 7,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Recent signups with profile details."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(User).where(User.created_at >= cutoff).order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    items = []
    for u in users:
        profile = u.profile
        items.append({
            "id": u.id,
            "email": u.email,
            "user_type": u.user_type.value,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat(),
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            "has_profile": profile is not None,
            "display_name": profile.display_name if profile else None,
            "city": profile.city if profile else None,
            "is_photo_verified": profile.is_photo_verified if profile else False,
            "is_income_verified": profile.is_income_verified if profile else False,
            "photo_count": len(profile.photos) if profile else 0,
            "is_seed": profile.is_seed if profile else False,
        })
    return items


@router.post("/users/{user_id}/verify-income")
async def manually_verify_income(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually mark a user's income as verified."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.profile:
        raise HTTPException(status_code=404, detail="User or profile not found")
    user.profile.is_income_verified = True
    await db.commit()
    return {"verified": True, "user_id": user_id}


@router.post("/users/{user_id}/verify-photo")
async def manually_verify_photo(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually mark a user's photos as verified."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.profile:
        raise HTTPException(status_code=404, detail="User or profile not found")
    user.profile.is_photo_verified = True
    await db.commit()
    return {"verified": True, "user_id": user_id}


@router.get("/reports")
async def get_reports(
    status: str = "all",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).order_by(Report.created_at.desc()).limit(50)
    )
    reports = result.scalars().all()

    items = []
    for r in reports:
        reporter_r = await db.execute(select(Profile).where(Profile.id == r.reporter_profile_id))
        reporter = reporter_r.scalar_one_or_none()
        reported_r = await db.execute(select(Profile).where(Profile.id == r.reported_profile_id))
        reported = reported_r.scalar_one_or_none()
        items.append({
            "id": r.id,
            "reporter": reporter.display_name if reporter else "Unknown",
            "reported": reported.display_name if reported else "Unknown",
            "reported_profile_id": r.reported_profile_id,
            "reason": r.reason.value,
            "details": r.details,
            "created_at": r.created_at.isoformat(),
        })
    return items


@router.get("/users")
async def get_users(
    page: int = 1,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset((page - 1) * 50).limit(50)
    )
    users = result.scalars().all()

    items = []
    for u in users:
        profile = u.profile
        items.append({
            "id": u.id,
            "email": u.email,
            "user_type": u.user_type.value,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "has_profile": profile is not None,
            "display_name": profile.display_name if profile else None,
            "is_seed": profile.is_seed if profile else False,
            "created_at": u.created_at.isoformat(),
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
        })
    return items


@router.get("/profiles")
async def get_profiles(
    page: int = 1,
    user_type: str = "",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List real profiles sorted by newest, with optional user_type filter."""
    from app.models.user import UserType
    from app.models.subscription import Subscription

    query = (
        select(User, Profile, Subscription)
        .join(Profile, Profile.user_id == User.id)
        .outerjoin(Subscription, Subscription.user_id == User.id)
        .where(Profile.is_seed == False)
        .order_by(User.created_at.desc())
    )

    if user_type == "sugar":
        query = query.where(User.user_type == UserType.SUGAR)
    elif user_type == "attractive":
        query = query.where(User.user_type == UserType.ATTRACTIVE)

    query = query.offset((page - 1) * 50).limit(50)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for u, p, s in rows:
        from datetime import date
        age = ""
        if p.date_of_birth:
            today = date.today()
            age = today.year - p.date_of_birth.year - ((today.month, today.day) < (p.date_of_birth.month, p.date_of_birth.day))

        items.append({
            "user_id": u.id,
            "email": u.email,
            "user_type": u.user_type.value,
            "display_name": p.display_name,
            "city": p.city,
            "state": p.state,
            "country": p.country,
            "gender": p.gender.value if p.gender else None,
            "age": age,
            "bio": p.bio[:100] + "..." if p.bio and len(p.bio) > 100 else p.bio,
            "headline": p.headline,
            "has_photos": bool(p.photos),
            "photo_count": len(p.photos) if p.photos else 0,
            "is_active": p.is_active,
            "subscription_tier": s.tier.value if s else "free",
            "created_at": u.created_at.isoformat(),
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
        })
    return items


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    if user.profile:
        user.profile.is_active = False
        user.profile.is_hidden = True
    await db.commit()
    return {"suspended": True, "user_id": user_id}


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    if user.profile:
        user.profile.is_active = True
        user.profile.is_hidden = False
    await db.commit()
    return {"unsuspended": True, "user_id": user_id}


# Verification endpoints

@router.get("/verifications")
async def get_verifications(
    status: str = "pending",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(VerificationRequest).order_by(VerificationRequest.created_at.desc())
    if status == "pending":
        query = query.where(VerificationRequest.status == VerificationStatus.PENDING)
    result = await db.execute(query.limit(50))
    reqs = result.scalars().all()

    items = []
    for r in reqs:
        user_r = await db.execute(select(User).where(User.id == r.user_id))
        user = user_r.scalar_one_or_none()
        items.append({
            "id": r.id,
            "user_id": r.user_id,
            "email": user.email if user else None,
            "display_name": user.profile.display_name if user and user.profile else None,
            "type": r.type.value,
            "status": r.status.value,
            "evidence_url": r.evidence_url,
            "notes": r.notes,
            "created_at": r.created_at.isoformat(),
        })
    return items


@router.post("/verifications/{request_id}/approve")
async def approve_verification(
    request_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VerificationRequest).where(VerificationRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    req.status = VerificationStatus.APPROVED
    req.reviewed_by = admin.email
    req.reviewed_at = datetime.utcnow()

    # Update the user's profile verification badges
    user_r = await db.execute(select(User).where(User.id == req.user_id))
    user = user_r.scalar_one_or_none()
    if user and user.profile:
        if req.type == VerificationType.PHOTO:
            user.profile.is_photo_verified = True
        elif req.type == VerificationType.INCOME:
            user.profile.is_income_verified = True

    await db.commit()
    return {"approved": True, "request_id": request_id}


@router.post("/verifications/{request_id}/reject")
async def reject_verification(
    request_id: int,
    reason: str = "Does not meet requirements",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VerificationRequest).where(VerificationRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    req.status = VerificationStatus.REJECTED
    req.reviewed_by = admin.email
    req.reviewed_at = datetime.utcnow()
    req.notes = reason

    await db.commit()
    return {"rejected": True, "request_id": request_id}


# User verification submission endpoint (not admin — any user can submit)

@router.post("/verify/submit")
async def submit_verification(
    type: VerificationType,
    evidence_url: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check for existing pending request
    existing = await db.execute(
        select(VerificationRequest).where(
            VerificationRequest.user_id == user.id,
            VerificationRequest.type == type,
            VerificationRequest.status == VerificationStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a pending verification request")

    req = VerificationRequest(
        user_id=user.id,
        type=type,
        evidence_url=evidence_url,
    )
    db.add(req)
    await db.commit()
    return {"submitted": True, "type": type.value}


# ─── Moderation Queue ───

@router.get("/flagged-messages")
async def get_flagged_messages(
    status: str = "pending",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get flagged messages. status: pending, reviewed, all."""
    query = select(Message).where(Message.is_flagged == True)
    if status == "pending":
        query = query.where(Message.reviewed_at == None)
    elif status == "reviewed":
        query = query.where(Message.reviewed_at != None)
    query = query.order_by(Message.created_at.desc()).limit(50)
    result = await db.execute(query)
    messages = result.scalars().all()

    return [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "sender_profile_id": m.sender_profile_id,
            "sender_name": m.sender.display_name if m.sender else None,
            "content": m.content,
            "flag_reason": m.flag_reason,
            "is_reviewed": m.reviewed_at is not None,
            "reviewed_at": m.reviewed_at.isoformat() if m.reviewed_at else None,
            "reviewed_by": m.reviewed_by,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.get("/flagged-profiles")
async def get_flagged_profiles(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get flagged profiles pending review."""
    result = await db.execute(
        select(Profile).where(Profile.is_flagged == True, Profile.reviewed_at == None)
        .order_by(Profile.created_at.desc()).limit(50)
    )
    profiles = result.scalars().all()
    return [
        {
            "id": p.id,
            "display_name": p.display_name,
            "bio": (p.bio or "")[:200],
            "flag_reason": p.flag_reason,
            "created_at": p.created_at.isoformat(),
        }
        for p in profiles
    ]


@router.post("/messages/{message_id}/review")
async def review_message(
    message_id: int,
    action: str,
    request: FastAPIRequest,
    reason: str | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Review a flagged message. action: dismiss, delete, suspend_user."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.reviewed_at = datetime.utcnow()
    message.reviewed_by = admin.email

    if action == "dismiss":
        pass  # Just mark as reviewed
    elif action == "delete":
        message.content = "[Removed by moderator]"
    elif action == "suspend_user":
        # Find and suspend the sender
        sender_profile_r = await db.execute(select(Profile).where(Profile.id == message.sender_profile_id))
        sender_profile = sender_profile_r.scalar_one_or_none()
        if sender_profile:
            sender_profile.is_active = False
            sender_profile.is_hidden = True
            sender_user_r = await db.execute(select(User).where(User.id == sender_profile.user_id))
            sender_user = sender_user_r.scalar_one_or_none()
            if sender_user:
                sender_user.is_active = False
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await log_action(
        db, actor_type="admin", actor_id=admin.id, actor_email=admin.email,
        action=f"review_message_{action}", resource_type="message", resource_id=message_id,
        details={"flag_reason": message.flag_reason, "admin_reason": reason},
        request=request,
    )
    await db.commit()
    return {"reviewed": True, "action": action}


@router.post("/profiles/{profile_id}/review")
async def review_profile(
    profile_id: int,
    action: str,
    request: FastAPIRequest,
    reason: str | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Review a flagged profile. action: dismiss, hide, suspend_user."""
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.reviewed_at = datetime.utcnow()
    profile.reviewed_by = admin.email

    if action == "dismiss":
        profile.is_flagged = False
        profile.flag_reason = None
    elif action == "hide":
        profile.is_hidden = True
    elif action == "suspend_user":
        profile.is_active = False
        profile.is_hidden = True
        user_r = await db.execute(select(User).where(User.id == profile.user_id))
        u = user_r.scalar_one_or_none()
        if u:
            u.is_active = False
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await log_action(
        db, actor_type="admin", actor_id=admin.id, actor_email=admin.email,
        action=f"review_profile_{action}", resource_type="profile", resource_id=profile_id,
        details={"flag_reason": profile.flag_reason, "admin_reason": reason},
        request=request,
    )
    await db.commit()
    return {"reviewed": True, "action": action}


# ─── Audit Log ───

@router.get("/audit-log")
async def get_audit_log(
    action: str | None = None,
    resource_type: str | None = None,
    page: int = 1,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Searchable audit log. Filter by action, resource_type."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    query = query.offset((page - 1) * 50).limit(50)

    result = await db.execute(query)
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "actor_email": e.actor_email,
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "details": e.details,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.post("/send-complete-profile-emails")
async def send_complete_profile_emails(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send 'complete your profile' email to all users without profiles."""
    import logging
    from app.services.email import send_complete_profile

    logger = logging.getLogger(__name__)

    # Find users who have no profile (not seed)
    result = await db.execute(
        select(User.email, User.user_type)
        .where(
            ~User.id.in_(select(Profile.user_id)),
            User.email.isnot(None),
        )
    )
    users = result.all()

    sent = 0
    for email, user_type in users:
        try:
            send_complete_profile(email, user_type.value)
            sent += 1
        except Exception as e:
            logger.warning("Failed to email %s: %s", email, e)

    return {"sent": sent, "total_without_profile": len(users)}


@router.post("/send-add-photo-emails")
async def send_add_photo_emails(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send 'add a photo' email to users with profiles but no photos."""
    import logging
    from app.services.email import send_add_photos
    from app.models.photo import Photo

    logger = logging.getLogger(__name__)

    # Profiles without photos (non-seed only)
    result = await db.execute(
        select(User.email, Profile.display_name)
        .join(Profile, Profile.user_id == User.id)
        .where(
            Profile.is_seed == False,
            ~Profile.id.in_(select(Photo.profile_id)),
        )
    )
    users = result.all()

    sent = 0
    for email, name in users:
        try:
            send_add_photos(email, name)
            sent += 1
        except Exception as e:
            logger.warning("Failed to email %s: %s", email, e)

    return {"sent": sent, "total_without_photos": len(users)}


@router.post("/send-sd-retention-emails")
async def send_sd_retention_emails(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send retention emails to paying sugar daddies. Call daily via cron.

    - Day 1 after subscription: profile boost email
    - Day 3 after subscription: activity summary email
    - Day 7 after subscription: first week recap email
    - Weekly: new members digest for all paying SDs
    """
    import logging
    from datetime import date
    from app.models.subscription import Subscription, SubscriptionTier
    from app.models.user import UserType
    from app.models.match import Like
    from app.models.engagement import ProfileView
    from app.services.email import (
        send_sd_day1_boost,
        send_sd_day3_activity,
        send_sd_day7_recap,
        send_new_members_digest,
        send_weekly_stats,
    )

    logger = logging.getLogger(__name__)
    now = datetime.utcnow()
    sent = {"day1": 0, "day3": 0, "day7": 0, "digest": 0, "stats": 0}

    # --- Day 1: subscription started ~1 day ago (±12h window) ---
    day1_start = now - timedelta(days=1, hours=12)
    day1_end = now - timedelta(hours=12)
    result = await db.execute(
        select(User.email, Profile.display_name)
        .join(Subscription, Subscription.user_id == User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            User.user_type == UserType.SUGAR,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
            Subscription.is_active == True,
            Subscription.started_at.between(day1_start, day1_end),
            Profile.is_seed == False,
        )
    )
    for email, name in result.all():
        try:
            send_sd_day1_boost(email, name)
            sent["day1"] += 1
        except Exception as e:
            logger.warning("Day1 boost failed for %s: %s", email, e)

    # --- Day 3: subscription started ~3 days ago (±12h window) ---
    day3_start = now - timedelta(days=3, hours=12)
    day3_end = now - timedelta(days=2, hours=12)
    result = await db.execute(
        select(User.email, Profile.display_name, Profile.id)
        .join(Subscription, Subscription.user_id == User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            User.user_type == UserType.SUGAR,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
            Subscription.is_active == True,
            Subscription.started_at.between(day3_start, day3_end),
            Profile.is_seed == False,
        )
    )
    for email, name, profile_id in result.all():
        try:
            # Count actual likes received
            likes_count = (await db.execute(
                select(func.count(Like.id)).where(Like.to_profile_id == profile_id)
            )).scalar() or 0
            send_sd_day3_activity(email, name, likes_count)
            sent["day3"] += 1
        except Exception as e:
            logger.warning("Day3 activity failed for %s: %s", email, e)

    # --- Day 7: subscription started ~7 days ago (±12h window) ---
    day7_start = now - timedelta(days=7, hours=12)
    day7_end = now - timedelta(days=6, hours=12)
    week_ago = now - timedelta(days=7)
    new_members_week = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )).scalar() or 0

    result = await db.execute(
        select(User.email, Profile.display_name)
        .join(Subscription, Subscription.user_id == User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            User.user_type == UserType.SUGAR,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
            Subscription.is_active == True,
            Subscription.started_at.between(day7_start, day7_end),
            Profile.is_seed == False,
        )
    )
    for email, name in result.all():
        try:
            send_sd_day7_recap(email, name, new_members_week)
            sent["day7"] += 1
        except Exception as e:
            logger.warning("Day7 recap failed for %s: %s", email, e)

    # --- Weekly digest + stats for ALL paying SDs ---
    # Gather new member previews (attractive members who joined this week)
    preview_result = await db.execute(
        select(Profile.display_name, Profile.date_of_birth, Profile.city)
        .join(User, User.id == Profile.user_id)
        .where(
            User.user_type == UserType.ATTRACTIVE,
            User.created_at >= week_ago,
            Profile.is_seed == False,
            Profile.is_active == True,
        )
        .order_by(User.created_at.desc())
        .limit(5)
    )
    today = date.today()
    member_previews = []
    for pname, dob, pcity in preview_result.all():
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day)) if dob else ""
        member_previews.append({"name": pname, "age": age, "city": pcity or ""})

    # Get all paying SDs
    all_paying = await db.execute(
        select(User.id, User.email, Profile.display_name, Profile.id)
        .join(Subscription, Subscription.user_id == User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            User.user_type == UserType.SUGAR,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
            Subscription.is_active == True,
            Profile.is_seed == False,
        )
    )
    for user_id, email, name, profile_id in all_paying.all():
        # Send new members digest
        if new_members_week > 0 and member_previews:
            try:
                send_new_members_digest(email, name, new_members_week, member_previews)
                sent["digest"] += 1
            except Exception as e:
                logger.warning("Digest failed for %s: %s", email, e)

        # Send weekly stats
        try:
            likes = (await db.execute(
                select(func.count(Like.id)).where(
                    Like.to_profile_id == profile_id,
                    Like.created_at >= week_ago,
                )
            )).scalar() or 0

            views = 0
            try:
                views = (await db.execute(
                    select(func.count(ProfileView.id)).where(
                        ProfileView.viewed_profile_id == profile_id,
                        ProfileView.created_at >= week_ago,
                    )
                )).scalar() or 0
            except Exception:
                pass

            # Search appearances approximated as profile views (no separate tracking)
            search_appearances = views

            send_weekly_stats(email, name, views, likes, search_appearances)
            sent["stats"] += 1
        except Exception as e:
            logger.warning("Stats failed for %s: %s", email, e)

    # --- Abandoned checkout: SDs who started checkout 1-3 days ago but never completed ---
    from app.models.funnel import FunnelEvent
    from app.services.email import send_abandoned_checkout, send_discount_offer
    from app.config import settings as app_settings

    abandon_start = now - timedelta(days=3)
    abandon_end = now - timedelta(days=1)

    # Users with checkout_started in the 1-3 day window
    started_result = await db.execute(
        select(FunnelEvent.user_id)
        .where(
            FunnelEvent.event == "checkout_started",
            FunnelEvent.user_type == "sugar",
            FunnelEvent.created_at.between(abandon_start, abandon_end),
        )
        .distinct()
    )
    started_user_ids = {row[0] for row in started_result.all() if row[0]}

    if started_user_ids:
        # Exclude users who have a checkout_completed event (ever)
        completed_result = await db.execute(
            select(FunnelEvent.user_id)
            .where(
                FunnelEvent.event == "checkout_completed",
                FunnelEvent.user_id.in_(started_user_ids),
            )
            .distinct()
        )
        completed_ids = {row[0] for row in completed_result.all() if row[0]}
        abandoned_ids = started_user_ids - completed_ids

        # Also exclude anyone with an active paid subscription
        if abandoned_ids:
            active_sub_result = await db.execute(
                select(Subscription.user_id)
                .where(
                    Subscription.user_id.in_(abandoned_ids),
                    Subscription.is_active == True,
                    Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
                )
            )
            active_sub_ids = {row[0] for row in active_sub_result.all()}
            abandoned_ids -= active_sub_ids

        # Send emails with discount offer
        sent["abandoned_checkout"] = 0
        coupon_url = f"{app_settings.FRONTEND_URL}/settings?tab=subscription&coupon={app_settings.FIRST_PURCHASE_COUPON_ID}"
        test_domains = ("@test.com", "@demo.com", "@meetyourplus.com")
        for uid in abandoned_ids:
            try:
                user_result = await db.execute(
                    select(User.email, Profile.display_name)
                    .join(Profile, Profile.user_id == User.id)
                    .where(User.id == uid, Profile.is_seed == False)
                )
                row = user_result.one_or_none()
                if row and not any(row[0].endswith(d) for d in test_domains):
                    send_abandoned_checkout(row[0], row[1])
                    send_discount_offer(row[0], row[1], coupon_url)
                    sent["abandoned_checkout"] += 1
            except Exception as e:
                logger.warning("Abandoned checkout email failed for user %s: %s", uid, e)
    else:
        sent["abandoned_checkout"] = 0

    return {"sent": sent}


@router.post("/send-abandoned-checkout-emails")
async def send_abandoned_checkout_emails(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send abandoned checkout emails to sugar daddies who started checkout but didn't finish.

    Targets SUGAR users with a checkout_started funnel event but:
    - No checkout_completed event
    - No active paid subscription
    - Not a test email
    """
    import logging
    from app.models.funnel import FunnelEvent
    from app.models.subscription import Subscription, SubscriptionTier
    from app.models.user import UserType
    from app.services.email import send_abandoned_checkout, send_discount_offer
    from app.config import settings as app_settings

    logger = logging.getLogger(__name__)

    # Find all users with checkout_started
    started_result = await db.execute(
        select(FunnelEvent.user_id)
        .where(
            FunnelEvent.event == "checkout_started",
            FunnelEvent.user_type == "sugar",
        )
        .distinct()
    )
    started_user_ids = {row[0] for row in started_result.all() if row[0]}

    if not started_user_ids:
        return {"sent": 0, "eligible": 0}

    # Exclude users who completed checkout
    completed_result = await db.execute(
        select(FunnelEvent.user_id)
        .where(
            FunnelEvent.event == "checkout_completed",
            FunnelEvent.user_id.in_(started_user_ids),
        )
        .distinct()
    )
    completed_ids = {row[0] for row in completed_result.all() if row[0]}
    abandoned_ids = started_user_ids - completed_ids

    if not abandoned_ids:
        return {"sent": 0, "eligible": 0}

    # Exclude anyone with active paid subscription
    active_sub_result = await db.execute(
        select(Subscription.user_id)
        .where(
            Subscription.user_id.in_(abandoned_ids),
            Subscription.is_active == True,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
        )
    )
    active_sub_ids = {row[0] for row in active_sub_result.all()}
    abandoned_ids -= active_sub_ids

    # Send emails with discount offer, excluding test domains
    coupon_url = f"{app_settings.FRONTEND_URL}/settings?tab=subscription&coupon={app_settings.FIRST_PURCHASE_COUPON_ID}"
    test_domains = ("@test.com", "@demo.com", "@meetyourplus.com")
    sent = 0
    for uid in abandoned_ids:
        try:
            user_result = await db.execute(
                select(User.email, Profile.display_name)
                .join(Profile, Profile.user_id == User.id)
                .where(
                    User.id == uid,
                    User.user_type == UserType.SUGAR,
                    Profile.is_seed == False,
                )
            )
            row = user_result.one_or_none()
            if row and not any(row[0].endswith(d) for d in test_domains):
                send_abandoned_checkout(row[0], row[1])
                send_discount_offer(row[0], row[1], coupon_url)
                sent += 1
        except Exception as e:
            logger.warning("Abandoned checkout email failed for user %s: %s", uid, e)

    return {"sent": sent, "eligible": len(abandoned_ids)}


# ─── Seed Profile Generation ───

@router.post("/seed-profiles")
async def seed_profiles(
    request_body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate realistic seed profiles for a given city.

    Request body:
        city: str — city name
        state: str — state/province
        country: str — country name
        count: int — number of profiles to generate (1-100)
        gender: str — "female" or "male"
    """
    import random
    import uuid
    from datetime import date, timedelta

    from app.models.profile import (
        Profile, Gender, BodyType, Education, IncomeRange,
        LifestyleExpectation, RelationshipStatus, Availability,
        DrinkingHabit, SmokingHabit, SexualOrientation, Pronouns,
        VALID_ARRANGEMENT_TYPES, VALID_INTERESTS,
    )
    from app.models.subscription import Subscription, SubscriptionTier
    from app.models.user import UserType
    from app.services.auth import hash_password
    from app.services.geocoder import geocode_city

    city = request_body.get("city", "").strip()
    state = request_body.get("state", "").strip()
    country = request_body.get("country", "United States").strip()
    count = int(request_body.get("count", 10))
    gender_str = request_body.get("gender", "female").strip().lower()

    if not city:
        raise HTTPException(status_code=400, detail="city is required")
    if count < 1 or count > 100:
        raise HTTPException(status_code=400, detail="count must be between 1 and 100")
    if gender_str not in ("female", "male"):
        raise HTTPException(status_code=400, detail="gender must be 'female' or 'male'")

    gender = Gender.FEMALE if gender_str == "female" else Gender.MALE

    # Geocode
    lat, lon = await geocode_city(city, state, country)

    # ── Name pools ──
    FEMALE_NAMES = [
        "Adriana", "Priya", "Katerina", "Mei-Lin", "Sienna", "Noor", "Camila",
        "Bianca", "Tatiana", "Yelena", "Amara", "Zara", "Daphne", "Iris", "Luna",
        "Valentina", "Freya", "Maren", "Paloma", "Suki", "Leilani", "Josephine",
        "Celeste", "Nia", "Sage", "Vera", "Ingrid", "Reina", "Soleil", "Anais",
        "Thalia", "Raven", "Ivy", "Opal", "Esme", "Mireille", "Yara", "Leila",
        "Saskia", "Gianna", "Marisol", "Anika", "Dahlia", "Elara", "Kira",
        "Saffron", "Rio", "Astrid", "Cleo", "Natasha", "Vivienne", "Ilana",
        "Brielle", "Soraya", "Mika", "Rhea", "Isadora", "Lilith", "Calista",
        "Aurelia", "Selene", "Zadie", "Margot", "Inara", "Noemi", "Waverly",
        "Tamsin", "Liora", "Eloise", "Milena", "Petra", "Ximena", "Azalea",
        "Tessa", "Nalini", "Claudia", "Seraphina", "Maia", "Romy", "Odette",
        "Harlow", "Zuri", "Ines", "Nadia", "Emberly", "Ariadne", "Lux",
        "Catalina", "Elektra", "Delphine", "Farrah", "Giselle", "Haven",
        "Julieta", "Kamila", "Layla", "Maeve", "Niamh", "Ophelia", "Quinn",
        "Ramona", "Seren", "Talia", "Uma", "Wren", "Xiomara", "Yael", "Zinnia",
    ]

    MALE_NAMES = [
        "Marcus", "Rajan", "Dimitri", "Alejandro", "Henrik", "Kenji", "Nikolai",
        "Lucian", "Rafael", "Idris", "Soren", "Matteo", "Darius", "Emilio",
        "Caspian", "Arlo", "Callum", "Ronan", "Jasper", "Bodhi", "Leandro",
        "Stellan", "Thiago", "Xavier", "Zain", "Felix", "Hugo", "Ivan",
        "Joaquin", "Kian", "Laszlo", "Mikhail", "Naveen", "Orion", "Pascal",
        "Quentin", "Rashid", "Sami", "Tobias", "Ulrich", "Viktor", "Wolfgang",
        "Youssef", "Zander", "Alistair", "Benedict", "Cyrus", "Dorian",
        "Everett", "Finnegan", "Gideon", "Heath", "Isaias", "Jules",
        "Kingston", "Lorenzo", "Magnus", "Niall", "Oscar", "Pierce",
        "Reginald", "Sterling", "Tristan", "Vernon", "Winston", "Axel",
        "Brennan", "Conrad", "Desmond", "Ellis", "Frederick", "Grant",
        "Harrison", "Irving", "Jude", "Kieran", "Lionel", "Montgomery",
        "Nolan", "Omar", "Preston", "Reed", "Sebastian", "Theodore",
        "Vaughn", "Walker", "Anders", "Bastian", "Cedric", "Drake",
        "Eamon", "Flynn", "Graham", "Holden", "Jensen", "Knox",
        "Lennox", "Marshall", "Nash", "Otis", "Palmer", "Rhett", "Sullivan",
    ]

    # ── Template-based unique content generation ──
    # Instead of fixed pools, combine templates with variables to produce
    # thousands of unique bios, headlines, and looking_for texts.

    # City-relevant universities and landmarks for bio templates
    CITY_UNIVERSITIES = {
        "san francisco": "UCSF", "los angeles": "UCLA", "new york": "NYU",
        "chicago": "UChicago", "houston": "Rice University", "dallas": "SMU",
        "fort worth": "TCU", "austin": "UT Austin", "miami": "University of Miami",
        "seattle": "UW", "denver": "CU Denver", "boston": "Boston University",
        "atlanta": "Emory", "phoenix": "ASU", "portland": "Portland State",
        "san diego": "UCSD", "philadelphia": "UPenn", "nashville": "Vanderbilt",
        "charlotte": "UNC Charlotte", "tampa": "USF", "las vegas": "UNLV",
        "minneapolis": "University of Minnesota", "detroit": "Wayne State",
        "pittsburgh": "Carnegie Mellon", "raleigh": "NC State",
        "columbus": "Ohio State", "salt lake city": "University of Utah",
        "kansas city": "UMKC", "orlando": "UCF", "san antonio": "UTSA",
    }

    CITY_INDUSTRIES = {
        "san francisco": ["tech", "biotech", "venture capital"],
        "los angeles": ["entertainment", "fashion", "tech"],
        "new york": ["finance", "media", "fashion"],
        "chicago": ["finance", "consulting", "food"],
        "houston": ["oil & gas", "medical", "aerospace"],
        "dallas": ["finance", "telecom", "real estate"],
        "fort worth": ["defense", "aerospace", "energy"],
        "austin": ["tech", "music", "startups"],
        "miami": ["real estate", "hospitality", "finance"],
        "seattle": ["tech", "aerospace", "biotech"],
        "denver": ["tech", "cannabis", "outdoor industry"],
        "boston": ["biotech", "finance", "education"],
        "atlanta": ["media", "logistics", "tech"],
        "phoenix": ["real estate", "healthcare", "tech"],
        "portland": ["tech", "creative", "sustainability"],
        "san diego": ["biotech", "defense", "tourism"],
        "nashville": ["healthcare", "music", "hospitality"],
        "tampa": ["finance", "healthcare", "tourism"],
        "las vegas": ["hospitality", "entertainment", "real estate"],
    }

    local_uni = CITY_UNIVERSITIES.get(city.lower(), f"{city} University")

    # ── BIO GENERATION: Mixed structural types for variety ──
    # Type 1 — Profession lead (30%)
    FEMALE_BIO_TYPE1 = [
        f"Nurse at {city} General. I study hard and clean up even harder.",
        "Marketing manager who accidentally became a foodie influencer.",
        f"Law student at {local_uni}. First gen, full ambition.",
        f"Flight attendant based in {city}. Rarely home but always worth the wait.",
        f"Real estate agent in {city}. I sell dreams during the day — looking for mine at night.",
        "Freelance photographer. I see beauty everywhere, especially in the mirror.",
        "Tech recruiter. I match people for a living — ironic that I'm here.",
        "Dental hygienist with a perfect smile and a dark sense of humor.",
        "Personal trainer. Yes, these arms are real. Yes, I'll cook for you too.",
        f"Grad student in psychology at {local_uni}. I'll analyze you, but in a fun way.",
        f"Bartender at a cocktail bar in {city}. I make great drinks and better conversation.",
        "Elementary school teacher. Patient, nurturing, and ready for adult conversation.",
        "Social media manager. My Instagram is curated; my personality is authentic.",
        "Veterinary tech. I'm gentle with animals and honest with people.",
        "Accountant by day. Surprisingly fun by night.",
        "Fashion buyer. I have taste in clothes, food, and men.",
        "Physical therapist. I fix people for a living — emotionally, I'm a work in progress.",
        "Yoga instructor. Flexible in every sense of the word.",
        "Executive assistant. I run someone's empire — now building my own.",
        "Biotech researcher. Smart is the new sexy, and I have the papers to prove it.",
        f"Interior designer in {city}. I make spaces beautiful — my life is no exception.",
        "Pastry chef. Sweet in the kitchen, spicy everywhere else.",
        "PR specialist. I spin stories for brands all day. Mine is way more interesting.",
        f"Dance instructor in {city}. I move well and I don't follow — I lead.",
        "Esthetician. I make people glow. You should see what I do for myself.",
    ]

    # Type 2 — Personality first (25%)
    FEMALE_BIO_TYPE2 = [
        "Sweet but direct. I know what I want and I'm not afraid to ask for it. Also obsessed with sushi.",
        "Loyal, spontaneous, and allergic to small talk. Buy me tacos and I'm yours.",
        "Warm but selective. I don't open up easily but when I do, you'll wish I never stop talking.",
        "Confident, curious, and a little too honest for my own good. You've been warned.",
        "Independent but not cold. I just know the difference between needing someone and wanting them.",
        "Driven and soft at the same time. I'll outwork you then cook you dinner.",
        "Introverted in crowds, magnetic one-on-one. I save my energy for people who deserve it.",
        "Ambitious but present. I won't cancel on you for work — unless it's really important.",
        "Low-maintenance energy, high-maintenance taste. I keep it simple but I like the best.",
        "Affectionate and direct. If I like you, you'll know. If I don't, you'll also know.",
        "Patient, thoughtful, and a little bit chaotic. Never boring though.",
        "Funny without trying. Smart without showing off. Pretty without filters.",
        "Opinionated but open-minded. I'll argue with you then make you breakfast.",
        "Calm energy with a wild imagination. I'm more fun than I look.",
        "Genuine and grounded. I've done the party phase — now I want depth.",
        "Emotionally intelligent and physically active. I run 5Ks and deep conversations.",
        "Nurturing without being a pushover. I'll take care of you if you earn it.",
        "Creative, curious, and terrible at pretending to be someone I'm not.",
        "Old soul in a young body. I'd rather share a bottle of wine than go clubbing.",
        "Playful but serious when it counts. I balance both well.",
        "Direct, feminine, and uninterested in games. Refreshing, right?",
        "Easygoing but not easy. There's a difference and I embody it.",
        "Bubbly on the outside, thoughtful on the inside. Layers.",
        "Fiercely loyal once you're in. Getting in is the hard part.",
        "Quiet confidence. I don't need to prove anything — I just am.",
    ]

    # Type 3 — One-liner witty (15%)
    FEMALE_BIO_TYPE3 = [
        "My therapist says I'm doing great. My bank account disagrees.",
        "I have the emotional range of a poet and the appetite of a linebacker.",
        "Looking for someone who texts back fast and picks restaurants faster.",
        "I'm the friend everyone asks for dating advice. The irony isn't lost on me.",
        "Fluent in sarcasm, kindness, and Spanish. Not always in that order.",
        "I'll steal your hoodies and your heart. In that order.",
        "If you can make me laugh, you can have whatever you want.",
        "I'm a 10 but I cry at commercials.",
        "Swipe right if you like girls who eat. Because I eat.",
        "I have a 401k and a tattoo you'll never find in public.",
        "Sweet face, sharp mouth. Handle with enthusiasm.",
        "I look innocent but my search history says otherwise.",
        "I'll bring the vibes. You bring the reservations.",
        "Not looking for a texting buddy. I want the real thing.",
        "I'm the plot twist you didn't see coming.",
        "Cute enough to stop you scrolling. Interesting enough to keep you.",
        "Half angel, half chaos. Depends on the day.",
        "I cook, I clean, I cuss. The full package.",
        "I don't chase — I attract. And here we are.",
        "Dangerously good at eye contact and parallel parking.",
        "Built different. Also built well.",
        "I'm a lot. But in the best way.",
        "My love language is quality time and acts of snacking.",
        "I'll outwork you Monday through Friday. Weekends I'm all yours.",
        "I look better in your shirt than you do.",
    ]

    # Type 4 — Question/hook opener (10%)
    FEMALE_BIO_TYPE4 = [
        "Ever met someone who's equally comfortable at a black-tie gala and a taco truck? That's me.",
        "What if I told you I can hold a conversation about philosophy AND reality TV?",
        "You know that girl who walks into a room and everyone notices? No? Let me introduce myself.",
        "What's better than a pretty face? A pretty face with opinions. Hi.",
        "Remember when dating felt exciting? I'm trying to bring that back.",
        "Do you ever meet someone and just know? I'm still waiting for that. Are you it?",
        "Want someone who'll challenge you intellectually and make you laugh until you cry? Found her.",
        "Know what's rare? A woman who's beautiful, smart, AND emotionally available. You're welcome.",
        "What do a nursing degree and a passport full of stamps have in common? Me.",
        "Looking for a reason to dress up on a Tuesday night. Are you it?",
        f"New to {city} and looking for someone to show me the spots tourists don't know about.",
        "Can you keep up with someone who does yoga at 6am and stays out until midnight?",
        "Tired of profiles that all sound the same? Same. That's why mine doesn't.",
        "What would you do with someone who actually listens? Because I do.",
        "Ready to stop swiping and start living? Me too. Let's go.",
        "Know what I bring to the table? I AM the table.",
        "Looking for the one who makes all the wrong ones make sense. Poetic? Maybe. True? Absolutely.",
        "What happens when ambition meets warmth? You get me.",
        "Ever met a woman who can code, cook, and carry a conversation in two languages?",
        "Want the girlfriend experience without the drama? That's literally my brand.",
    ]

    # Type 5 — Story snippet (10%)
    FEMALE_BIO_TYPE5 = [
        f"Moved to {city} two years ago for a job. Stayed for the food. Now looking for someone to share both.",
        f"Quit my corporate job last year. Started over in {city}. Best decision I ever made — now I just need better company.",
        "Grew up in a small town, moved to the city, and discovered I like expensive taste with humble roots.",
        f"I came to {city} on a one-way ticket with two suitcases. Three years later I have a career, a cat, and zero regrets.",
        "My friends set me up on this app after my third 'I'm focusing on myself' speech. They might be right.",
        "Used to think I needed to have everything figured out before dating. Turns out, life is more fun when you figure it out together.",
        f"Left my hometown at 18. Traveled through Europe. Landed in {city}. Still looking for someone who makes me want to stay put.",
        "I studied abroad in Paris and never quite recovered. Now I chase that feeling in food, art, and people.",
        "My last relationship taught me what I don't want. Now I'm here for what I do.",
        "Spent my twenties building a career. Now I want someone to celebrate the wins with.",
        f"I moved to {city} knowing nobody. Built a whole life. The only thing missing? Someone to come home to.",
        "After years of saying 'I'm too busy to date,' I finally made time. So make it worth it.",
        "Took a solo trip last month and realized every beautiful sunset is better with someone next to you.",
        "My mom keeps asking when I'm bringing someone home for the holidays. Help me shut her up.",
        f"Fell in love with {city} the first week I moved here. Ready to fall for a person next.",
        "I turned 25 and decided I'm done with situationships. Looking for something with a future.",
        "Used to be the girl who 'doesn't need anyone.' Still don't need anyone — but I want someone.",
        f"Been in {city} for five years. Know all the best restaurants. Need someone to eat with.",
        "I laughed through my last breakup. Not because it was funny — because I knew something better was coming.",
        "Started a business at 22. It failed. Started another at 24. It didn't. Now I want a personal life.",
    ]

    # Type 6 — List style (5%)
    FEMALE_BIO_TYPE6 = [
        "Three things: I cook better than your mom, I'll beat you at Scrabble, and I look incredible in red.",
        "Facts: bilingual, can parallel park on the first try, and I remember everyone's birthday.",
        "What you're getting: great conversation, spontaneous adventures, and someone who actually laughs at your jokes.",
        "The basics: 5'6\", loves to cook, hates small talk, will absolutely steal your fries.",
        "Non-negotiables: honesty, effort, and someone who knows how to plan a date.",
        "Pros: loyal, funny, great cook. Cons: I will reorganize your closet without asking.",
        "Three truths: I've never been on a bad first date, I make killer cocktails, and I'm a morning person (sorry).",
        "The short version: smart, pretty, kind, impatient with boring people.",
        "What I offer: warmth, wit, killer pasta, and undivided attention when you're talking.",
        "About me in bullets: dancer, reader, foodie, cat mom, hopeless romantic pretending to be cynical.",
        "Ingredients: one part ambition, two parts affection, a dash of chaos.",
        "Resume: fluent in French, can do a backflip, makes friends with every dog on the street.",
        "Three words my friends use: loyal, extra, and worth-it.",
        "My highlights: solo-traveled 12 countries, can cook Thai food from scratch, killer at darts.",
        "Quick facts: Scorpio, oldest sibling, works in tech, weekend baker, terrible driver.",
        "The elevator pitch: beautiful, kind, ambitious, and I remember your coffee order after one time.",
        "Checklist: good taste, good heart, good hair, bad at texting back (working on it).",
        "Top 3: deep conversations at 2am, trying new restaurants, and making people feel seen.",
        "My skills: I can read a room, grill a steak, and make anyone feel comfortable in five minutes.",
        "Selling points: I'm low drama, high energy, and I give the best gifts.",
    ]

    # Type 7 — Minimalist (5%)
    FEMALE_BIO_TYPE7 = [
        "25. Bilingual. Ambitious. Cute. Here.",
        "Soft heart. Strong will.",
        "Pretty. Patient. Picky.",
        "All substance. Zero drama.",
        "Smart, sweet, selective.",
        "Less talk. More action.",
        "Quality over everything.",
        "Rare. Not desperate.",
        "Worth the effort.",
        "Depth over surface.",
        "Genuine article.",
        "Simple: I know my worth.",
        "Warm. Driven. Real.",
        "Not for everyone. Maybe for you.",
        "The one your mom warned you about — in the best way.",
        "Understated and unforgettable.",
        "What you see is what you get. And it's a lot.",
        "No games. Just chemistry.",
        "Low-key extraordinary.",
        "I said what I said.",
    ]

    # ── MALE BIO TYPES (successful men in their 40s-50s) ──

    # Type 1 — Profession lead (30%)
    MALE_BIO_TYPE1 = [
        f"Sold my last company at 34. Now I have time but nobody interesting to spend it with.",
        f"Finance exec in {city}. I work hard and play harder, but play alone too often.",
        f"Real estate developer in {city}. I build things — looking for something I can't build myself.",
        "Retired military officer. Disciplined, direct, generous. Still early enough to enjoy life.",
        f"Tech founder in {city}. My code compiles but my dating life doesn't.",
        f"Surgeon at {city} Medical Center. Steady hands, strong opinions about restaurants.",
        "Private equity partner. I don't talk about work at dinner unless you ask.",
        f"Architect with my own firm in {city}. I design spaces and I'm intentional about everything.",
        "Portfolio manager. I take calculated risks professionally and personally.",
        f"Restaurateur with three locations in {city}. I'll cook for you on the first date.",
        "Management consultant. I fly weekly, but I always come home to someone worth coming home to.",
        "Venture capitalist. I bet on people for a living. I have good instincts.",
        f"Commercial real estate in {city}. I own buildings you've walked past.",
        "Orthopedic surgeon. Long hours but I always make time for what matters.",
        "Import/export. I travel to Asia quarterly and Europe annually. Life is global.",
        f"Construction company owner in {city}. Started as a laborer at 19, now I run 200 people.",
        "Cardiologist. I know a thing or two about hearts — professionally and otherwise.",
        "Hedge fund analyst turned independent investor. Semi-retired at 47.",
        "Pharmaceutical executive. I run clinical trials — but I believe in chemistry.",
        f"Defense contractor based in {city}. Discipline and loyalty are non-negotiable.",
        f"Own a chain of gyms across {city}. Built it from one location and never looked back.",
        "Corporate attorney. I argue for a living. At home, I'd rather listen.",
        f"Tech VP at a Fortune 500 in {city}. I've made my money. Now I want meaning.",
        "Oral surgeon. My hands are steady and my patience is long.",
        "Franchise owner. Multiple locations, one very organized life. Room for the right person.",
    ]

    # Type 2 — Personality first (25%)
    MALE_BIO_TYPE2 = [
        "Straightforward, generous, and allergic to drama. I know what I want and I go after it.",
        "Old-fashioned about chivalry, modern about everything else. I open doors and I listen.",
        "Calm, confident, and genuinely curious about people. Success didn't change who I am.",
        "Direct but warm. I won't waste your time and I won't let you waste mine.",
        "I lead boardrooms all week. On weekends I just want good food, good wine, and better company.",
        "Protective without being possessive. Generous without keeping score. That's me.",
        "Patient, decisive, and comfortable in silence. Not everyone needs to fill every gap with noise.",
        "I've earned the right to be selective. And I choose quality over quantity — always.",
        "Competitive in business, easygoing in relationships. I leave the intensity at the office.",
        "Loyal to a fault. If you're my person, I'll move mountains. Getting there is the challenge.",
        "I value discretion, depth, and someone who can hold a conversation over dinner.",
        "Not flashy. Not loud. Just solid. The kind of man you can rely on completely.",
        "I've built everything else. Now I want the thing money can't buy — genuine connection.",
        "Generous with my time, my attention, and yes, my resources — for the right person.",
        "Successful enough to not need to prove it. Secure enough to let you be yourself.",
        "I spent my 30s building an empire. My 40s are for enjoying it with someone special.",
        "I don't need to be the center of attention. I'd rather make you the center of mine.",
        "Results-oriented in business, romance-oriented in life. I know how to balance both.",
        "Mature but not boring. I have my life together but I still know how to have fun.",
        "Self-made and self-aware. Two things that took decades to build.",
        "I treat people well because I can, not because I have to. That's a choice.",
        "Composed under pressure. Attentive when it matters. Present.",
        "Grounded, intentional, and done with superficial connections.",
        "I've lived enough to know what matters. Now I'm looking for who matters.",
        "The kind of man who remembers details — your coffee order, your mother's birthday, the story you told once.",
    ]

    # Type 3 — One-liner witty (15%)
    MALE_BIO_TYPE3 = [
        "I have a corner office and nobody to send flowers to.",
        "My accountant is thrilled with me. My dating life needs work.",
        "Three homes, zero someone-to-come-home-to. Fixing that.",
        "I've negotiated billion-dollar deals but I still can't pick a restaurant.",
        "Divorced, not damaged. Wiser, not bitter. Ready, not desperate.",
        "I fly first class and still prefer a home-cooked meal.",
        "My ex-wife got the house. I got the freedom. Both of us won.",
        "I'm the guy your dad would approve of. Your friends might be jealous.",
        "Rich in experiences. Also the other kind. But that's not why you should swipe.",
        "I have a boat. What I don't have is someone who looks good on it.",
        "Financially secure, emotionally available. Apparently that's rare.",
        "Built a company from my garage. Now my garage has a Porsche in it.",
        "I'm too old for games but too young to give up on love.",
        "My passport has more stamps than my dating profile has matches.",
        "I work hard so I can play harder. Need a plus-one for the playing part.",
        "I tip 30% and remember your birthday. Not bragging — just facts.",
        "Turns out money can't buy happiness. But it can buy dinner. Let's start there.",
        "CEO by title, home chef by passion. The apron stays on.",
        "I've climbed literal mountains. The dating app feels harder somehow.",
        "I'm the calm in the storm. Also the one paying for the storm insurance.",
        "My kids say I'm embarrassing. My colleagues say I'm impressive. Somewhere in between is the truth.",
        "I've been told I age like wine. Still waiting to be uncorked.",
        "I can fix anything except my own love life. That's what this is for.",
        "I have a wine collection and nobody to share it with. That's a crime.",
        "Semi-retired, fully interested. In you, specifically.",
    ]

    # Type 4 — Question/hook opener (10%)
    MALE_BIO_TYPE4 = [
        "What does a man with everything except companionship do? Apparently, join this app.",
        "Ever met someone who built a business from nothing and still cooks Sunday dinner? That's me.",
        "What good is a beautiful life if you experience it alone?",
        "Know what's rarer than financial success? Someone genuine to share it with.",
        "Want to travel business class to anywhere in the world next month? I just need to know who's coming.",
        f"Looking for someone who loves {city} as much as I do. Know every restaurant. Need a dinner partner.",
        "What's the point of a lake house with no one in the passenger seat on the drive up?",
        "Ever notice how the best meals are the ones you share? I eat alone too often.",
        "What if I told you I can fly you anywhere by Friday? The question is: where?",
        "Ready for someone who actually plans dates instead of asking 'wyd'?",
        "Want a man who listens more than he talks? I'm all ears.",
        "What happens when someone who has everything meets someone who IS everything?",
        "Looking for a reason to leave the office early. Are you it?",
        "Know what money taught me? That experiences matter more. I just need the right co-pilot.",
        "Ever dated someone who shows up? Not just texts — actually shows up? That's what I do.",
        "What's the move when you've achieved every goal except the personal one?",
        "Interested in someone who treats Tuesday like Saturday? Because I can.",
        "What would you do with a man who has nothing to prove and everything to give?",
        "Tired of men who talk about what they'll do 'someday'? I already did it. Now what?",
        "Ready to be spoiled by someone who means it? Not performatively — genuinely?",
    ]

    # Type 5 — Story snippet (10%)
    MALE_BIO_TYPE5 = [
        f"Built my first business at 26 in a garage. Sold it at 38. Moved to {city}. Still figuring out the personal life part.",
        "Divorced at 42. Took a year to myself. Traveled. Reflected. Now I'm ready — properly this time.",
        f"Grew up with nothing. Put myself through school. Now I live in {city} in a house I built. Only thing missing is the right person in it.",
        "My kids are in college now. The nest is empty and the silence is deafening. Looking for noise — the good kind.",
        f"Moved to {city} for business ten years ago. Made it home. But a house isn't a home without someone to share it with.",
        "After my divorce I threw myself into work. Made more money than I know what to do with. Turns out, that's not the answer.",
        "Sold my shares last year. For the first time in twenty years, I have time. Now I need someone worth spending it with.",
        f"I commute between {city} and New York weekly. I know every airport lounge. I'd rather know your favorite restaurant.",
        "Spent my 30s in boardrooms. My 40s at Michelin-starred restaurants — alone. Time to change that.",
        "My last relationship ended because I worked too much. I've since restructured. Ready to be present.",
        "Retired early. Traveled alone for a year. Every beautiful sunset reminded me I had no one to share it with.",
        f"I've been in {city} for fifteen years. Built a name here. Now I want someone who knows me beyond the name.",
        "My friends are all married. I'm the last one standing. Not because I can't commit — because I won't settle.",
        "Took my company public last year. Everyone celebrated with me. Then I went home alone. That's the part I want to fix.",
        "I spent decades building security. Now I want warmth.",
        f"First generation immigrant. Made it to the top in {city}. My parents are proud but keep asking about grandchildren.",
        "After 20 years of grinding, I woke up one day and realized I have it all — except someone to wake up next to.",
        "My life looks perfect on paper. In person, there's a chair at my dinner table that's been empty too long.",
        "Built three companies. Lost two. The one that survived made everything else possible. Now I want the personal win.",
        "I fly private and eat alone. Something's wrong with that picture.",
    ]

    # Type 6 — List style (5%)
    MALE_BIO_TYPE6 = [
        "The basics: self-made, generous, knows how to cook, still has all his hair.",
        "What I offer: stability, spontaneity, world travel, and undivided attention.",
        "Three things: I plan dates you'll brag about, I listen like I mean it, and I always pick up the check.",
        "Non-negotiables: honesty, effort, and someone who values time over things.",
        "Pros: financially secure, emotionally available, great taste. Cons: I snore.",
        "The pitch: I have resources, time, and intention. I'm looking for chemistry and authenticity.",
        "Facts: two businesses, one ex-wife, zero drama, full heart.",
        "What you get: loyalty, generosity, adventure, and someone who follows through.",
        "Key stats: 48, divorced, 6'1\", active, successful, ready.",
        "My life in bullets: early riser, weekend sailor, home chef, terrible dancer, great provider.",
        "Three truths: I've never cancelled a date, I tip more than I should, and I remember everything you tell me.",
        "Highlights: built a company from nothing, raised good kids, still bench press my body weight.",
        "The short version: established, generous, direct, done with games.",
        "What I bring: resources, emotional intelligence, stability, and the best restaurant reservations.",
        "Quick bio: entrepreneur, father, traveler, optimist, terrible golfer despite expensive lessons.",
        "Resume: self-made, well-traveled, well-read, well-cooked-for if you're lucky.",
        "Three words my friends use: solid, generous, loyal.",
        "My credentials: I built something real. Now I want something real.",
        "Selling points: I show up, I follow through, and I know how to treat someone.",
        "The essentials: secure, intentional, warm, and still young enough to enjoy it all.",
    ]

    # Type 7 — Minimalist (5%)
    MALE_BIO_TYPE7 = [
        "Self-made. Selective. Ready.",
        "Built it all. Now what?",
        "Substance. Stability. Chemistry.",
        "Less noise. More depth.",
        "Established. Available. Intentional.",
        "I've earned this chapter.",
        "Done building. Ready to share.",
        "Results, not promises.",
        "I show up. Always.",
        "Quiet confidence. Real generosity.",
        "The genuine article.",
        "No games. Just substance.",
        "Everything except someone. Fixing that.",
        "Worth your time.",
        "I back words with action.",
        "Proven. Present. Interested.",
        "Earned it. Ready to share it.",
        "Real man. Real intentions.",
        "Zero pretense. Full commitment.",
        "Simple: I keep my word.",
    ]

    # Bio type weights: Type1=30%, Type2=25%, Type3=15%, Type4=10%, Type5=10%, Type6=5%, Type7=5%
    BIO_TYPE_WEIGHTS = [30, 25, 15, 10, 10, 5, 5]

    FEMALE_BIO_POOLS = [
        FEMALE_BIO_TYPE1, FEMALE_BIO_TYPE2, FEMALE_BIO_TYPE3,
        FEMALE_BIO_TYPE4, FEMALE_BIO_TYPE5, FEMALE_BIO_TYPE6, FEMALE_BIO_TYPE7,
    ]
    MALE_BIO_POOLS = [
        MALE_BIO_TYPE1, MALE_BIO_TYPE2, MALE_BIO_TYPE3,
        MALE_BIO_TYPE4, MALE_BIO_TYPE5, MALE_BIO_TYPE6, MALE_BIO_TYPE7,
    ]

    # ── Headline generation: adjectives + descriptor patterns ──
    FEMALE_ADJECTIVES = [
        "Ambitious", "Sweet", "Classy", "Bold", "Magnetic",
        "Confident", "Elegant", "Sharp", "Warm", "Selective",
        "Direct", "Radiant", "Cultured", "Fearless", "Graceful",
        "Independent", "Genuine", "Polished", "Spirited", "Intriguing",
        "Sophisticated", "Vivacious", "Witty", "Alluring", "Unapologetic",
        "Driven", "Effortless", "Fierce", "Thoughtful", "Magnetic",
    ]
    FEMALE_DESCRIPTORS = [
        "and unapologetic",
        "but not naive",
        "with a wild side",
        "and worth the effort",
        f"in {city}",
        "with high standards",
        "and impossible to forget",
        "— the real deal",
        "with substance to match",
        "and selective about it",
        "with no time for games",
        "in every sense",
        "beyond first impressions",
        "with depth you won't expect",
        "and ready for something real",
    ]

    MALE_ADJECTIVES = [
        "Distinguished", "Self-made", "Established", "Generous", "Polished",
        "Ambitious", "Successful", "Refined", "Confident", "Driven",
        "Sophisticated", "Cultured", "Decisive", "Grounded", "Intentional",
        "Accomplished", "Discreet", "Worldly", "Experienced", "Direct",
        "Principled", "Magnetic", "Genuine", "Focused", "Commanding",
        "Thoughtful", "Elegant", "Sharp", "Composed", "Substantial",
    ]
    MALE_DESCRIPTORS = [
        "and looking for exceptional",
        "with real intentions",
        "— not here to waste time",
        f"in {city}",
        "and ready to invest in someone",
        "with a generous spirit",
        "beyond the boardroom",
        "and genuinely curious about you",
        "with substance to share",
        "who values partnership",
        "and unapologetically high-value",
        "with more to offer than fits here",
        "— the real thing",
        "in business and in life",
        "with room for the right person",
    ]

    # ── Looking-for generation: want + style + extra ──
    FEMALE_WANTS = [
        "Someone genuine", "Someone established", "Someone confident",
        "A man who knows what he wants", "Someone generous",
        "A successful man", "Someone emotionally intelligent",
        "A man with substance", "Someone who values quality",
        "A real gentleman", "Someone driven", "A man who follows through",
        "Someone secure in himself", "A partner who shows up",
        "Someone worldly",
    ]
    FEMALE_STYLES = [
        "who values quality time over grand gestures.",
        "who treats me like a partner, not a project.",
        "who knows the difference between spending and investing.",
        "who leads with generosity and follows through.",
        "who challenges me intellectually and supports me emotionally.",
        "who makes me feel chosen, not convenient.",
        "who appreciates beauty and intelligence equally.",
        "who understands that the best things are shared.",
        "who is consistent without being boring.",
        "who brings stability and excitement in equal measure.",
    ]
    FEMALE_EXTRAS = [
        " Consistency matters more than grand gestures.",
        " I bring warmth, loyalty, and excellent company in return.",
        " Mutual respect is non-negotiable for me.",
        " I want someone who makes both our lives better.",
        " I believe relationships should elevate both people.",
    ]

    MALE_WANTS = [
        "A genuine connection", "Someone beautiful and intelligent",
        "A confident woman", "Real chemistry",
        "Someone who matches my energy", "An ambitious woman",
        "A partner with substance", "Someone authentic",
        "Elegance and warmth", "A woman who knows herself",
        "Someone who values discretion", "A real spark",
        "Companionship with depth", "Someone who sees me clearly",
        "A woman with her own ambitions",
    ]
    MALE_STYLES = [
        "who appreciates what I bring to the table.",
        "who makes me want to come home earlier.",
        "who is comfortable at a black-tie event and on a Sunday morning.",
        "who values experiences over things.",
        "who reciprocates loyalty with loyalty.",
        "who challenges me and inspires me.",
        "who enjoys being taken care of without taking advantage.",
        "who brings light into a busy life.",
        "who values quality time as much as I do.",
        "who is genuine in a world of profiles.",
    ]
    MALE_EXTRAS = [
        " I have everything I need — except the right person.",
        " I'm better with a partner. Full stop.",
        " Real attraction, real compatibility, real potential.",
        " I invest emotionally and in every other way.",
        " I don't do surface-level anymore.",
    ]

    def generate_bio(is_female_profile: bool, used_bios: set) -> str:
        """Generate a unique bio by first picking a structural TYPE, then a template from that type.

        Types and weights:
        1. Profession lead (30%) — leads with job/career
        2. Personality first (25%) — leads with character traits
        3. One-liner witty (15%) — single punchy sentence
        4. Question/hook opener (10%) — starts with a question or hook
        5. Story snippet (10%) — mini narrative about life
        6. List style (5%) — bullet/list format
        7. Minimalist (5%) — ultra-short, 2-5 words
        """
        pools = FEMALE_BIO_POOLS if is_female_profile else MALE_BIO_POOLS
        for _ in range(100):  # avoid infinite loop
            # Pick a type based on weights
            type_idx = random.choices(range(7), weights=BIO_TYPE_WEIGHTS, k=1)[0]
            pool = pools[type_idx]
            bio = random.choice(pool)
            if bio not in used_bios:
                used_bios.add(bio)
                return bio
        # Fallback: pick any bio from any pool
        type_idx = random.choices(range(7), weights=BIO_TYPE_WEIGHTS, k=1)[0]
        return random.choice(pools[type_idx])

    def generate_headline(is_female_profile: bool, used_headlines: set) -> str:
        """Generate a unique headline from adjective + descriptor."""
        adjectives = FEMALE_ADJECTIVES if is_female_profile else MALE_ADJECTIVES
        descriptors = FEMALE_DESCRIPTORS if is_female_profile else MALE_DESCRIPTORS
        for _ in range(100):
            adj = random.choice(adjectives)
            desc = random.choice(descriptors)
            headline = f"{adj} {desc}"
            if headline not in used_headlines:
                used_headlines.add(headline)
                return headline
        return random.choice(adjectives) + " " + random.choice(descriptors)

    def generate_looking_for(is_female_profile: bool, used_looking: set) -> str:
        """Generate unique looking_for from want + style + extra."""
        wants = FEMALE_WANTS if is_female_profile else MALE_WANTS
        styles = FEMALE_STYLES if is_female_profile else MALE_STYLES
        extras = FEMALE_EXTRAS if is_female_profile else MALE_EXTRAS
        for _ in range(100):
            w = random.choice(wants)
            s = random.choice(styles)
            e = random.choice(extras)
            text = f"{w} {s}{e}"
            if text not in used_looking:
                used_looking.add(text)
                return text
        return random.choice(wants) + " " + random.choice(styles) + random.choice(extras)

    # ── Occupation pools ──
    FEMALE_OCCUPATIONS = [
        "Registered Nurse", "Fashion Model", "Graduate Student", "Marketing Manager",
        "Real Estate Agent", "Fitness Trainer", "Freelance Artist", "Elementary Teacher",
        "Bartender & Mixologist", "Fashion Stylist", "Professional Dancer", "Photographer",
        "Corporate Lawyer", "UX Designer", "Dental Hygienist", "Esthetician",
        "Event Planner", "Sommelier", "Travel Blogger", "Pastry Chef",
        "Architecture Student", "PR Specialist", "Yoga Instructor", "Journalist",
        "Medical Student", "Graphic Designer", "Social Worker", "Fashion Buyer",
        "Pilates Instructor", "Freelance Illustrator", "ICU Nurse", "Data Analyst",
        "Physical Therapist", "Account Executive", "Ceramics Artist", "Theatre Actress",
        "Biotech Researcher", "Florist", "Executive Assistant", "Classical Musician",
        "Nutritionist", "Marine Biologist", "Boutique Owner", "Occupational Therapist",
        "Software Engineer", "Barista", "Interior Designer", "Music Producer",
        "Veterinary Technician", "Clinical Psychology Student",
    ]

    MALE_OCCUPATIONS = [
        "CEO & Founder", "Surgeon", "Tech Entrepreneur", "Real Estate Developer",
        "Private Equity Partner", "Retired Finance Executive", "Restaurateur",
        "M&A Attorney", "Portfolio Manager", "Serial Entrepreneur",
        "Orthopedic Surgeon", "Commercial Pilot", "Investment Banker", "Architect",
        "Hospitality Executive", "Dermatologist", "Venture Capitalist",
        "Construction Company Owner", "Management Consultant", "Cardiologist",
        "CFO", "Yacht Broker", "IP Attorney", "Dentist",
        "Independent Investor", "Executive Coach", "Franchise Owner",
        "Radiologist", "Import/Export Business Owner", "Software Company CEO",
        "Plastic Surgeon", "Financial Advisor", "Defense Contractor",
        "Winery Owner", "Pharmaceutical Executive", "Civil Engineer",
        "Tech VP", "Sports Agent", "Anesthesiologist", "Commercial Real Estate",
    ]

    # ── Weighted random helpers ──
    def weighted_choice(options: list, weights: list):
        return random.choices(options, weights=weights, k=1)[0]

    def random_body_type() -> BodyType:
        return weighted_choice(
            [BodyType.SLIM, BodyType.ATHLETIC, BodyType.CURVY, BodyType.AVERAGE, BodyType.FULL_FIGURED, BodyType.OTHER],
            [30, 25, 20, 15, 5, 5],
        )

    def random_lifestyle_expectation() -> LifestyleExpectation:
        return weighted_choice(
            [LifestyleExpectation.NEGOTIABLE, LifestyleExpectation.PRACTICAL, LifestyleExpectation.MODERATE, LifestyleExpectation.SUBSTANTIAL, LifestyleExpectation.HIGH],
            [10, 15, 35, 30, 10],
        )

    def random_income_range() -> IncomeRange:
        return weighted_choice(
            [IncomeRange.R100K_250K, IncomeRange.R250K_500K, IncomeRange.R500K_1M, IncomeRange.R1M_5M],
            [20, 40, 25, 15],
        )

    def random_age(gender_val: Gender) -> date:
        if gender_val == Gender.FEMALE:
            # Weighted toward 23-28
            age = weighted_choice(
                list(range(21, 33)),
                [3, 5, 10, 15, 15, 15, 12, 10, 6, 4, 3, 2],
            )
        else:
            # Males 35-58
            age = random.randint(35, 58)
        today = date.today()
        dob = today.replace(year=today.year - age)
        # Randomize the month/day
        random_days = random.randint(0, 364)
        dob = dob - timedelta(days=random_days)
        return dob

    def random_arrangement_types() -> list[str]:
        all_types = list(VALID_ARRANGEMENT_TYPES)
        k = random.randint(2, 3)
        return random.sample(all_types, min(k, len(all_types)))

    def random_interests() -> list[str]:
        all_interests = list(VALID_INTERESTS)
        k = random.randint(3, 6)
        return random.sample(all_interests, min(k, len(all_interests)))

    def random_height(gender_val: Gender) -> int:
        if gender_val == Gender.FEMALE:
            return random.randint(155, 178)  # ~5'1" to 5'10"
        else:
            return random.randint(170, 195)  # ~5'7" to 6'5"

    ETHNICITIES_FEMALE = [
        "Caucasian", "Latina", "Asian", "Black", "Middle Eastern",
        "Mixed", "South Asian", "Eastern European", "Mediterranean",
        "Southeast Asian", "Brazilian", "Caribbean", "Pacific Islander",
    ]
    ETHNICITIES_MALE = [
        "Caucasian", "Latino", "Asian", "Black", "Middle Eastern",
        "Mixed", "South Asian", "Mediterranean", "Eastern European",
    ]

    EDUCATION_OPTIONS = [Education.BACHELORS, Education.MASTERS, Education.SOME_COLLEGE, Education.DOCTORATE, Education.OTHER]
    EDUCATION_WEIGHTS_F = [35, 25, 20, 10, 10]
    EDUCATION_WEIGHTS_M = [25, 35, 5, 20, 15]

    LANGUAGES_OPTIONS = [
        "English", "English, Spanish", "English, French", "English, Portuguese",
        "English, Mandarin", "English, Russian", "English, Arabic",
        "English, Italian", "English, Korean", "English, Japanese",
        "English, Hindi", "English, German", "English, Spanish, French",
        "English, Portuguese, Spanish", "English, Tagalog",
    ]

    RELATIONSHIP_STATUSES = [RelationshipStatus.SINGLE, RelationshipStatus.DIVORCED, RelationshipStatus.SEPARATED, RelationshipStatus.OPEN]
    REL_WEIGHTS_F = [70, 10, 10, 10]
    REL_WEIGHTS_M = [30, 30, 10, 30]

    AVAILABILITY_OPTIONS = [Availability.FLEXIBLE, Availability.WEEKDAYS, Availability.WEEKENDS, Availability.EVENINGS, Availability.TRAVEL_READY]

    IDEAL_FIRST_DATES_F = [
        "A rooftop cocktail bar with a view and good conversation.",
        "Dinner at a quiet restaurant where we can actually talk.",
        "A wine tasting followed by a walk through the city.",
        "Sushi omakase — you can tell a lot about someone by what they order.",
        "Coffee first, then see where the afternoon takes us.",
        "An art gallery opening, then drinks somewhere intimate.",
        "A long walk and honest conversation. Fancy dates can come later.",
        "Somewhere with great food and no pretension.",
        "A speakeasy. I like places you have to know about.",
        "Brunch — because the best conversations happen over eggs and champagne.",
        "A sunset boat ride. I know, I'm a romantic.",
        "A jazz club. Music tells you more about someone than small talk.",
        "Something spontaneous — surprise me.",
        "A farmers market followed by cooking together at home.",
        "Dinner and live music. Good food and a soundtrack.",
    ]

    IDEAL_FIRST_DATES_M = [
        "Dinner at my favorite restaurant — I already have a table.",
        "A private wine tasting. I know a place.",
        "Cocktails at a rooftop bar with a view worth sharing.",
        "A sailing afternoon followed by waterfront dinner.",
        "Coffee at a quiet spot, then a walk. Let's see if we click.",
        "Front-row seats to something cultural — theatre, symphony, or a gallery.",
        "Sushi at the chef's counter. I like watching artists work.",
        "A helicopter tour of the city followed by dinner.",
        "My yacht, sunset, your favorite champagne. Simple.",
        "Somewhere discreet with excellent food and real conversation.",
    ]

    # ── Build unique profiles ──
    is_female = gender == Gender.FEMALE
    names_pool = FEMALE_NAMES[:] if is_female else MALE_NAMES[:]
    occupations_pool = FEMALE_OCCUPATIONS[:] if is_female else MALE_OCCUPATIONS[:]
    ethnicities_pool = ETHNICITIES_FEMALE if is_female else ETHNICITIES_MALE
    ideal_dates_pool = IDEAL_FIRST_DATES_F[:] if is_female else IDEAL_FIRST_DATES_M[:]

    random.shuffle(names_pool)
    random.shuffle(occupations_pool)
    random.shuffle(ideal_dates_pool)

    if count > len(names_pool):
        raise HTTPException(status_code=400, detail=f"count exceeds available unique names ({len(names_pool)})")

    user_type = UserType.ATTRACTIVE if is_female else UserType.SUGAR
    seeking = Gender.MALE if is_female else Gender.FEMALE
    pronouns = Pronouns.SHE_HER if is_female else Pronouns.HE_HIM
    orientation = SexualOrientation.STRAIGHT

    city_slug = city.lower().replace(" ", "-")[:20]
    created = 0

    # Track used combinations to avoid duplicates within this batch
    used_bios: set = set()
    used_headlines: set = set()
    used_looking_for: set = set()

    for i in range(count):
        uid = uuid.uuid4().hex[:12]
        email = f"seed-{city_slug}-{uid}@seed.plus.io"
        pw_hash = hash_password(uuid.uuid4().hex)

        user = User(
            email=email,
            password_hash=pw_hash,
            user_type=user_type,
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        await db.flush()  # Get user.id

        dob = random_age(gender)
        education = weighted_choice(EDUCATION_OPTIONS, EDUCATION_WEIGHTS_F if is_female else EDUCATION_WEIGHTS_M)
        rel_status = weighted_choice(RELATIONSHIP_STATUSES, REL_WEIGHTS_F if is_female else REL_WEIGHTS_M)

        profile = Profile(
            user_id=user.id,
            display_name=names_pool[i],
            bio=generate_bio(is_female, used_bios),
            headline=generate_headline(is_female, used_headlines),
            date_of_birth=dob,
            gender=gender,
            seeking_gender=seeking,
            sexual_orientation=orientation,
            pronouns=pronouns,
            city=city,
            state=state,
            country=country,
            latitude=lat,
            longitude=lon,
            height_cm=random_height(gender),
            body_type=random_body_type(),
            ethnicity=random.choice(ethnicities_pool),
            education=education,
            occupation=occupations_pool[i % len(occupations_pool)],
            languages=random.choice(LANGUAGES_OPTIONS),
            income_range=random_income_range() if not is_female else None,
            lifestyle_expectation=random_lifestyle_expectation() if is_female else None,
            looking_for=generate_looking_for(is_female, used_looking_for),
            arrangement_types=random_arrangement_types(),
            interests=random_interests(),
            relationship_status=rel_status,
            availability=random.choice(AVAILABILITY_OPTIONS),
            drinking=random.choice([DrinkingHabit.SOCIALLY, DrinkingHabit.SOCIALLY, DrinkingHabit.NEVER, DrinkingHabit.REGULARLY]),
            smoking=random.choice([SmokingHabit.NEVER, SmokingHabit.NEVER, SmokingHabit.NEVER, SmokingHabit.OCCASIONALLY]),
            has_children=random.choice([False, False, False, True]) if not is_female else False,
            ideal_first_date=ideal_dates_pool[i % len(ideal_dates_pool)],
            is_active=True,
            is_seed=True,
        )
        db.add(profile)

        subscription = Subscription(
            user_id=user.id,
            tier=SubscriptionTier.FREE,
            is_active=True,
        )
        db.add(subscription)

        created += 1

    await db.commit()

    return {"created": created, "city": city, "gender": gender_str}


@router.get("/attribution")
async def get_attribution(
    days: int = 90,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Attribution dashboard: which sources drive signups and paying customers."""
    from app.models.funnel import FunnelEvent
    from app.models.subscription import Subscription, SubscriptionTier

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Get all signup events with metadata
    result = await db.execute(
        select(FunnelEvent.user_id, FunnelEvent.metadata_)
        .where(
            FunnelEvent.event == "signup",
            FunnelEvent.created_at >= cutoff,
        )
    )
    signup_rows = result.all()

    # Build lookup: user_id -> attribution data
    user_attribution: dict[int, dict] = {}
    for user_id, meta in signup_rows:
        if not user_id:
            continue
        source = "direct"
        if meta:
            if meta.get("utm_source"):
                source = meta["utm_source"]
            elif meta.get("referrer"):
                source = meta["referrer"]
        user_attribution[user_id] = {
            "source": source,
            "landing_page": (meta or {}).get("landing_page", "/"),
            "utm_campaign": (meta or {}).get("utm_campaign", ""),
        }

    if not user_attribution:
        return {"sources": [], "landing_pages": [], "utm_campaigns": []}

    user_ids = list(user_attribution.keys())

    # Check which users created profiles
    profile_result = await db.execute(
        select(Profile.user_id).where(
            Profile.user_id.in_(user_ids),
            Profile.is_seed == False,
        )
    )
    profile_user_ids = {row[0] for row in profile_result.all()}

    # Check which users paid (premium or diamond subscription)
    paid_result = await db.execute(
        select(Subscription.user_id).where(
            Subscription.user_id.in_(user_ids),
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
        )
    )
    paid_user_ids = {row[0] for row in paid_result.all()}

    # Aggregate by source
    source_data: dict[str, dict] = {}
    for uid, attr in user_attribution.items():
        src = attr["source"]
        if src not in source_data:
            source_data[src] = {"signups": 0, "profiles": 0, "paid": 0}
        source_data[src]["signups"] += 1
        if uid in profile_user_ids:
            source_data[src]["profiles"] += 1
        if uid in paid_user_ids:
            source_data[src]["paid"] += 1

    sources = sorted(
        [{"source": k, **v} for k, v in source_data.items()],
        key=lambda x: x["signups"],
        reverse=True,
    )

    # Aggregate by landing page
    page_data: dict[str, int] = {}
    for attr in user_attribution.values():
        page = attr["landing_page"] or "/"
        page_data[page] = page_data.get(page, 0) + 1

    landing_pages = sorted(
        [{"page": k, "signups": v} for k, v in page_data.items()],
        key=lambda x: x["signups"],
        reverse=True,
    )[:20]

    # Aggregate by UTM campaign
    campaign_data: dict[str, dict] = {}
    for uid, attr in user_attribution.items():
        camp = attr["utm_campaign"]
        if not camp:
            continue
        if camp not in campaign_data:
            campaign_data[camp] = {"signups": 0, "paid": 0}
        campaign_data[camp]["signups"] += 1
        if uid in paid_user_ids:
            campaign_data[camp]["paid"] += 1

    utm_campaigns = sorted(
        [{"campaign": k, **v} for k, v in campaign_data.items()],
        key=lambda x: x["signups"],
        reverse=True,
    )

    return {
        "sources": sources,
        "landing_pages": landing_pages,
        "utm_campaigns": utm_campaigns,
    }


@router.post("/check-churn-risk")
async def check_churn_risk(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Find paying SDs inactive >3 days and send admin alerts."""
    import logging
    from app.models.subscription import Subscription, SubscriptionTier
    from app.models.user import UserType
    from app.services.email import send_admin_churn_alert

    logger = logging.getLogger(__name__)
    cutoff = datetime.utcnow() - timedelta(days=3)

    # Paying SDs whose last_seen is older than 3 days (or null)
    result = await db.execute(
        select(User.email, Profile.display_name, Profile.city, User.last_seen, Subscription.tier)
        .join(Subscription, Subscription.user_id == User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(
            User.user_type == UserType.SUGAR,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
            Subscription.is_active == True,
            Profile.is_seed == False,
            (User.last_seen < cutoff) | (User.last_seen == None),
        )
    )
    rows = result.all()

    sent = 0
    now = datetime.utcnow()
    for email, name, city, last_seen, tier in rows:
        days_inactive = (now - last_seen).days if last_seen else 999
        try:
            send_admin_churn_alert(
                admin_email="cmoralestech@gmail.com",
                user_email=email,
                display_name=name or "",
                city=city or "",
                days_inactive=days_inactive,
                tier=tier.value,
            )
            sent += 1
        except Exception as e:
            logger.warning("Churn alert failed for %s: %s", email, e)

    return {"sent": sent, "at_risk": len(rows)}


@router.post("/send-weekly-report")
async def send_weekly_report(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Gather weekly metrics and send revenue report email."""
    import logging
    from app.models.subscription import Subscription, SubscriptionTier
    from app.models.funnel import FunnelEvent
    from app.services.email import send_weekly_revenue_report

    logger = logging.getLogger(__name__)
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    # MRR: count active paid subs * their tier price
    subs_result = await db.execute(
        select(Subscription.tier)
        .where(
            Subscription.is_active == True,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
        )
    )
    tier_prices = {"premium": 49.99, "diamond": 99.99}
    mrr = 0.0
    for (tier,) in subs_result.all():
        mrr += tier_prices.get(tier.value, 0)

    # New subscribers this week
    new_subs = (await db.execute(
        select(func.count(Subscription.id))
        .where(
            Subscription.started_at >= week_ago,
            Subscription.tier.in_([SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND]),
        )
    )).scalar() or 0

    # New signups this week
    new_signups = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )).scalar() or 0

    # Cancellations this week (subs that became free/inactive this week)
    cancellations = (await db.execute(
        select(func.count(FunnelEvent.id))
        .where(
            FunnelEvent.event == "subscription_cancelled",
            FunnelEvent.created_at >= week_ago,
        )
    )).scalar() or 0

    # Top 3 signup sources (from acquisition_source events)
    source_col = FunnelEvent.metadata_["source"].astext.label("source")
    sources_result = await db.execute(
        select(
            source_col,
            func.count(FunnelEvent.id).label("cnt"),
        )
        .where(
            FunnelEvent.event == "acquisition_source",
            FunnelEvent.created_at >= week_ago,
        )
        .group_by(source_col)
        .order_by(func.count(FunnelEvent.id).desc())
        .limit(3)
    )
    top_sources = [{"source": row.source, "count": row.cnt} for row in sources_result.all()]

    # Also check referrer-based sources from signup events
    if not top_sources:
        referrer_col = FunnelEvent.metadata_["referrer"].astext.label("source")
        referrer_result = await db.execute(
            select(
                referrer_col,
                func.count(FunnelEvent.id).label("cnt"),
            )
            .where(
                FunnelEvent.event == "signup",
                FunnelEvent.created_at >= week_ago,
            )
            .group_by(referrer_col)
            .order_by(func.count(FunnelEvent.id).desc())
            .limit(3)
        )
        top_sources = [{"source": row.source or "Direct", "count": row.cnt} for row in referrer_result.all()]

    # Total real profiles (non-seed)
    total_profiles = (await db.execute(
        select(func.count(Profile.id)).where(Profile.is_seed == False)
    )).scalar() or 0

    # Total funnel events this week
    total_events = (await db.execute(
        select(func.count(FunnelEvent.id)).where(FunnelEvent.created_at >= week_ago)
    )).scalar() or 0

    try:
        send_weekly_revenue_report(
            to="cmoralestech@gmail.com",
            mrr=mrr,
            new_subs=new_subs,
            new_signups=new_signups,
            cancellations=cancellations,
            top_sources=top_sources,
            total_profiles=total_profiles,
            total_events=total_events,
        )
        return {
            "sent": True,
            "mrr": round(mrr, 2),
            "new_subs": new_subs,
            "new_signups": new_signups,
            "cancellations": cancellations,
            "top_sources": top_sources,
            "total_profiles": total_profiles,
            "total_events": total_events,
        }
    except Exception as e:
        logger.error("Weekly report email failed: %s", e)
        return {"sent": False, "error": str(e)}


# ─── Daily Cron (all automations in one call) ───

async def _require_cron_secret(x_cron_secret: str = Header("")):
    """Verify the X-Cron-Secret header matches the configured secret."""
    if not settings.CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET not configured")
    if x_cron_secret != settings.CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid cron secret")


@router.post("/daily-cron", dependencies=[Depends(_require_cron_secret)])
async def daily_cron(
    request: FastAPIRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run ALL automated email tasks in one call. Authenticated via X-Cron-Secret header.

    Calls in sequence:
    1. SD retention emails (onboarding day 1/3/7 + weekly digest/stats + abandoned checkout)
    2. Standalone abandoned checkout emails
    3. Churn risk alerts
    4. Newsletter drip emails
    """
    logger = logging.getLogger(__name__)
    results = {}

    # 1. SD retention emails
    try:
        # Build a fake admin user to satisfy the internal function signature
        admin_result = await db.execute(
            select(User).where(User.email.in_(ADMIN_EMAILS)).limit(1)
        )
        admin_user = admin_result.scalar_one_or_none()
        if admin_user:
            retention = await send_sd_retention_emails(admin=admin_user, db=db)
            results["sd_retention"] = retention
        else:
            results["sd_retention"] = {"skipped": "no admin user found"}
    except Exception as e:
        logger.error("Daily cron - sd_retention failed: %s", e)
        results["sd_retention"] = {"error": str(e)}

    # 2. Abandoned checkout emails
    try:
        if admin_user:
            abandoned = await send_abandoned_checkout_emails(admin=admin_user, db=db)
            results["abandoned_checkout"] = abandoned
        else:
            results["abandoned_checkout"] = {"skipped": "no admin user found"}
    except Exception as e:
        logger.error("Daily cron - abandoned_checkout failed: %s", e)
        results["abandoned_checkout"] = {"error": str(e)}

    # 3. Churn risk
    try:
        if admin_user:
            churn = await check_churn_risk(admin=admin_user, db=db)
            results["churn_risk"] = churn
        else:
            results["churn_risk"] = {"skipped": "no admin user found"}
    except Exception as e:
        logger.error("Daily cron - churn_risk failed: %s", e)
        results["churn_risk"] = {"error": str(e)}

    # 4. Newsletter drip
    try:
        drip = await _run_newsletter_drip(db)
        results["newsletter_drip"] = drip
    except Exception as e:
        logger.error("Daily cron - newsletter_drip failed: %s", e)
        results["newsletter_drip"] = {"error": str(e)}

    return {"status": "completed", "results": results}


async def _run_newsletter_drip(db: AsyncSession) -> dict:
    """Run newsletter drip logic inline (same as /api/newsletter/drip)."""
    from app.models.funnel import FunnelEvent
    from app.services.email import send_newsletter_drip_comparison, send_newsletter_drip_cta

    logger = logging.getLogger(__name__)
    now = datetime.utcnow()

    day3_start = now - timedelta(days=3, hours=12)
    day3_end = now - timedelta(days=2, hours=12)
    result = await db.execute(
        select(FunnelEvent.metadata_["email"].as_string())
        .where(
            FunnelEvent.event == "newsletter_subscribe",
            FunnelEvent.created_at.between(day3_start, day3_end),
        )
    )
    day3_emails = [r[0] for r in result.all() if r[0]]

    day7_start = now - timedelta(days=7, hours=12)
    day7_end = now - timedelta(days=6, hours=12)
    result = await db.execute(
        select(FunnelEvent.metadata_["email"].as_string())
        .where(
            FunnelEvent.event == "newsletter_subscribe",
            FunnelEvent.created_at.between(day7_start, day7_end),
        )
    )
    day7_emails = [r[0] for r in result.all() if r[0]]

    sent = {"comparison": 0, "cta": 0}
    for email in day3_emails:
        try:
            send_newsletter_drip_comparison(email)
            sent["comparison"] += 1
        except Exception as e:
            logger.warning("Drip comparison failed for %s: %s", email, e)

    for email in day7_emails:
        try:
            send_newsletter_drip_cta(email)
            sent["cta"] += 1
        except Exception as e:
            logger.warning("Drip CTA failed for %s: %s", email, e)

    return {"sent": sent}


# ─── SB → SD Invite Email Blast ───

@router.post("/send-sb-invite-emails")
async def send_sb_invite_emails(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send invite-a-SD emails to all attractive members with profiles.

    Each SB gets a referral link they can share with successful men.
    When the referred SD subscribes to Diamond, the SB earns $25/month.
    """
    from app.models.user import UserType
    from app.models.referral import ReferralLink, generate_referral_code
    from app.services.email import send_sb_invite_sd

    logger = logging.getLogger(__name__)
    test_domains = ("@test.com", "@demo.com", "@seed.plus.io")

    # Find all attractive members with profiles (non-seed, real emails)
    result = await db.execute(
        select(User.id, User.email, Profile.display_name)
        .join(Profile, Profile.user_id == User.id)
        .where(
            User.user_type == UserType.ATTRACTIVE,
            Profile.is_seed == False,
            Profile.is_active == True,
        )
    )
    members = result.all()

    sent = 0
    for user_id, email, display_name in members:
        if any(email.endswith(d) for d in test_domains):
            continue

        try:
            # Get or create referral link
            link_result = await db.execute(
                select(ReferralLink).where(ReferralLink.user_id == user_id)
            )
            link = link_result.scalar_one_or_none()
            if not link:
                code = generate_referral_code()
                link = ReferralLink(user_id=user_id, code=code)
                db.add(link)
                await db.flush()

            referral_code = link.custom_slug or link.code
            send_sb_invite_sd(email, display_name or "there", referral_code)
            sent += 1
        except Exception as e:
            logger.warning("SB invite email failed for %s: %s", email, e)

    await db.commit()
    return {"sent": sent, "total_eligible": len(members)}
