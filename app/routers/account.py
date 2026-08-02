from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.profile import Profile
from app.models.safety import Block
from app.services.audit import log_action
from app.models.notification_prefs import NotificationPreferences
from app.services.auth import hash_password, verify_password
from app.routers.profiles import profile_to_response

router = APIRouter(prefix="/api/account", tags=["account"])


# --- Password change ---

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    await log_action(db, actor_type="user", actor_id=user.id, action="change_password", resource_type="user", resource_id=user.id, request=request)
    await db.commit()
    return {"message": "Password changed successfully"}


# --- Notification preferences ---

class NotificationPrefsResponse(BaseModel):
    new_match: bool
    new_message: bool
    new_like: bool
    profile_view: bool
    email_matches: bool
    email_messages: bool
    email_promotions: bool
    email_tips: bool

    model_config = {"from_attributes": True}


class NotificationPrefsUpdate(BaseModel):
    new_match: bool | None = None
    new_message: bool | None = None
    new_like: bool | None = None
    profile_view: bool | None = None
    email_matches: bool | None = None
    email_messages: bool | None = None
    email_promotions: bool | None = None
    email_tips: bool | None = None


async def _get_or_create_notif_prefs(user_id: int, db: AsyncSession) -> NotificationPreferences:
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = NotificationPreferences(user_id=user_id)
        db.add(prefs)
        await db.flush()
    return prefs


@router.get("/notifications", response_model=NotificationPrefsResponse)
async def get_notification_prefs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_or_create_notif_prefs(user.id, db)
    await db.commit()
    return prefs


@router.patch("/notifications", response_model=NotificationPrefsResponse)
async def update_notification_prefs(
    data: NotificationPrefsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_or_create_notif_prefs(user.id, db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    return prefs


# --- Blocked users list (with profile info) ---

class BlockedUserResponse(BaseModel):
    profile_id: int
    display_name: str
    city: str | None
    blocked_at: str


@router.get("/blocked", response_model=list[BlockedUserResponse])
async def get_blocked_users(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        return []

    result = await db.execute(
        select(Block).where(Block.blocker_profile_id == user.profile.id)
    )
    blocks = result.scalars().all()

    responses = []
    if blocks:
        pids = [b.blocked_profile_id for b in blocks]
        profiles_result = await db.execute(select(Profile).where(Profile.id.in_(pids)))
        profiles_map = {p.id: p for p in profiles_result.scalars().all()}

        for block in blocks:
            p = profiles_map.get(block.blocked_profile_id)
            if p:
                responses.append(BlockedUserResponse(
                    profile_id=p.id,
                    display_name=p.display_name,
                    city=p.city,
                    blocked_at=block.created_at.isoformat(),
                ))
    return responses


# --- Account deactivation ---

@router.post("/deactivate")
async def deactivate_account(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.is_active = False
    if user.profile:
        user.profile.is_active = False
        user.profile.is_hidden = True
    await log_action(db, actor_type="user", actor_id=user.id, action="deactivate_account", resource_type="user", resource_id=user.id, request=request)
    await db.commit()
    return {"message": "Account deactivated. You can reactivate by logging in again."}


# --- Full data deletion (GDPR) ---

@router.delete("/delete-account")
async def delete_account(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete all user data. Irreversible. GDPR Article 17 compliance."""
    import sqlalchemy

    user_id = user.id
    profile_id = user.profile.id if user.profile else None

    # Audit log BEFORE deletion — proves GDPR compliance without retaining deleted data
    await log_action(
        db, actor_type="user", actor_id=user_id, actor_email=user.email,
        action="gdpr_delete_account", resource_type="user", resource_id=user_id,
        details={"had_profile": profile_id is not None, "email_domain": user.email.split("@")[-1] if user.email else None},
        request=request,
    )
    await db.flush()  # Ensure audit log is written before deletion

    # Every column that can point at this profile. Both directions matter: the
    # previous version deleted only rows where the member was the actor, so a
    # like *received* from someone else survived and the profile delete then
    # failed on a foreign key — leaving the account intact and the request 500.
    profile_refs = [
        ("messages", ["sender_profile_id"]),
        ("likes", ["from_profile_id", "to_profile_id"]),
        ("favorites", ["from_profile_id", "profile_id"]),
        ("profile_views", ["viewer_profile_id", "viewed_profile_id"]),
        ("blocks", ["blocker_profile_id", "blocked_profile_id"]),
        ("reports", ["reporter_profile_id", "reported_profile_id"]),
        ("boosts", ["profile_id"]),
        ("photos", ["profile_id"]),
        ("destination_interests", ["profile_id"]),
        ("conversations", ["profile1_id", "profile2_id"]),
        ("matches", ["profile1_id", "profile2_id"]),
    ]
    user_refs = [
        "verification_requests", "member_verifications", "funnel_events",
        "referral_earnings", "referrals", "referral_links",
        "privacy_settings", "notification_preferences", "subscriptions",
    ]

    # Which columns actually exist, resolved up front. Postgres aborts the
    # entire transaction on any error, so discovering a missing table by
    # letting the statement fail poisons every delete that follows — the
    # deletion then reports success having removed nothing.
    existing_rows = (
        await db.execute(
            sqlalchemy.text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public'"
            )
        )
    ).all()
    existing: dict[str, set[str]] = {}
    for table_name, column_name in existing_rows:
        existing.setdefault(table_name, set()).add(column_name)

    if profile_id:
        for table, columns in profile_refs:
            present = [c for c in columns if c in existing.get(table, set())]
            if not present:
                continue
            where = " OR ".join(f"{c} = :pid" for c in present)
            await db.execute(
                sqlalchemy.text(f"DELETE FROM {table} WHERE {where}"), {"pid": profile_id}
            )

        await db.execute(
            sqlalchemy.text("DELETE FROM profiles WHERE id = :pid"), {"pid": profile_id}
        )

    for table in user_refs:
        if "user_id" not in existing.get(table, set()):
            continue
        await db.execute(
            sqlalchemy.text(f"DELETE FROM {table} WHERE user_id = :uid"), {"uid": user_id}
        )

    # Delete user
    await db.execute(sqlalchemy.text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    await db.commit()

    return {"message": "Account and all associated data permanently deleted."}
