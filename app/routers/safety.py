from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.profile import Profile
from app.models.match import Like, Match
from app.models.message import Conversation
from app.services.audit import log_action
from app.models.safety import Block, Report, ReportReason

router = APIRouter(prefix="/api/safety", tags=["safety"])


class BlockRequest:
    pass


@router.post("/block/{profile_id}", status_code=201)
async def block_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")
    if profile_id == user.profile.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    # Check target exists
    target = await db.execute(select(Profile).where(Profile.id == profile_id))
    if not target.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Profile not found")

    # Check if already blocked
    existing = await db.execute(
        select(Block).where(
            Block.blocker_profile_id == user.profile.id,
            Block.blocked_profile_id == profile_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already blocked")

    block = Block(blocker_profile_id=user.profile.id, blocked_profile_id=profile_id)
    db.add(block)

    # Remove any existing match between the two
    pid = user.profile.id
    p1, p2 = min(pid, profile_id), max(pid, profile_id)
    match_result = await db.execute(
        select(Match).where(Match.profile1_id == p1, Match.profile2_id == p2)
    )
    match = match_result.scalar_one_or_none()
    if match:
        match.is_active = False

    # Remove likes
    await db.execute(
        Like.__table__.delete().where(
            or_(
                (Like.from_profile_id == pid) & (Like.to_profile_id == profile_id),
                (Like.from_profile_id == profile_id) & (Like.to_profile_id == pid),
            )
        )
    )

    await db.commit()
    return {"blocked": True}


@router.delete("/block/{profile_id}")
async def unblock_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    result = await db.execute(
        select(Block).where(
            Block.blocker_profile_id == user.profile.id,
            Block.blocked_profile_id == profile_id,
        )
    )
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    await db.delete(block)
    await db.commit()
    return {"unblocked": True}


@router.get("/blocked")
async def get_blocked_profiles(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        return []

    result = await db.execute(
        select(Block).where(Block.blocker_profile_id == user.profile.id)
    )
    blocks = result.scalars().all()
    return [{"profile_id": b.blocked_profile_id, "created_at": b.created_at} for b in blocks]


@router.post("/report/{profile_id}", status_code=201)
async def report_profile(
    profile_id: int,
    reason: ReportReason,
    request: Request,
    details: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")
    if profile_id == user.profile.id:
        raise HTTPException(status_code=400, detail="Cannot report yourself")

    # Check target exists
    target_r = await db.execute(select(Profile).where(Profile.id == profile_id))
    target_profile = target_r.scalar_one_or_none()
    if not target_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    report = Report(
        reporter_profile_id=user.profile.id,
        reported_profile_id=profile_id,
        reason=reason,
        details=details[:1000] if details else None,
    )
    db.add(report)

    # Audit log
    await log_action(
        db, actor_type="user", actor_id=user.id,
        action="submit_report", resource_type="profile", resource_id=profile_id,
        details={"reason": reason.value, "has_details": bool(details)},
        request=request,
    )

    # Trafficking reports get immediate escalation
    if reason == ReportReason.HUMAN_TRAFFICKING:
        target_profile.is_flagged = True
        target_profile.flag_reason = "Human trafficking report"
        await log_action(
            db, actor_type="system", action="auto_flag_trafficking",
            resource_type="profile", resource_id=profile_id,
            details={"reporter_id": user.profile.id},
        )
    else:
        # Check report threshold for auto-action
        report_count_r = await db.execute(
            select(func.count(Report.id)).where(Report.reported_profile_id == profile_id)
        )
        report_count = (report_count_r.scalar() or 0) + 1  # +1 for current report not yet committed

        if report_count >= 5 and target_profile.is_active:
            # Auto-suspend
            target_profile.is_active = False
            target_profile.is_hidden = True
            target_user_r = await db.execute(select(User).where(User.id == target_profile.user_id))
            target_user = target_user_r.scalar_one_or_none()
            if target_user:
                target_user.is_active = False
            await log_action(
                db, actor_type="system", action="auto_suspend",
                resource_type="user", resource_id=target_profile.user_id,
                details={"report_count": report_count, "trigger": "5_reports"},
            )
        elif report_count >= 3 and not target_profile.is_flagged:
            # Auto-flag for review
            target_profile.is_flagged = True
            target_profile.flag_reason = f"Auto-flagged: {report_count} reports"
            await log_action(
                db, actor_type="system", action="auto_flag_reports",
                resource_type="profile", resource_id=profile_id,
                details={"report_count": report_count},
            )

    await db.commit()
    return {"reported": True}
