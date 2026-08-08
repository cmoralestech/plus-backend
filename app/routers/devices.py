"""Device registration for push notifications."""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.device import DeviceToken
from app.models.user import User

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceRegister(BaseModel):
    token: str = Field(min_length=10, max_length=255)
    platform: str = Field(default="ios", pattern="^(ios|android)$")
    device_name: str | None = Field(default=None, max_length=120)


@router.post("/register")
@limiter.limit("20/hour")
async def register_device(
    request: Request,
    data: DeviceRegister,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register or re-register this device against the signed-in member.

    Re-registering an existing token reassigns it. That matters: without it, a
    device that changed hands would keep delivering the previous owner's
    matches and messages to whoever holds it now.
    """
    if not data.token.startswith(("ExponentPushToken[", "ExpoPushToken[")):
        raise HTTPException(status_code=400, detail="Not a valid Expo push token")

    existing = (
        await db.execute(select(DeviceToken).where(DeviceToken.token == data.token))
    ).scalar_one_or_none()

    if existing:
        existing.user_id = user.id
        existing.platform = data.platform
        existing.device_name = data.device_name
        existing.is_active = True
        existing.last_used_at = datetime.utcnow()
    else:
        db.add(
            DeviceToken(
                user_id=user.id,
                token=data.token,
                platform=data.platform,
                device_name=data.device_name,
                last_used_at=datetime.utcnow(),
            )
        )

    await db.commit()
    return {"registered": True}


@router.post("/unregister")
async def unregister_device(
    data: DeviceRegister,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop delivering to this device — used on sign-out.

    Scoped to the caller's own tokens so a token string learned elsewhere can't
    be used to silence somebody else's notifications.
    """
    existing = (
        await db.execute(
            select(DeviceToken).where(
                DeviceToken.token == data.token,
                DeviceToken.user_id == user.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.is_active = False
        await db.commit()

    # Reported the same either way: whether a token belongs to somebody else
    # isn't something an unregister call should reveal.
    return {"unregistered": True}
