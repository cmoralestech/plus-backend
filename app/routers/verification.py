"""Identity and financial verification.

Public surface is two booleans. Amounts, bands, documents and the basis of
qualification stay private to the member and are never returned to anyone else.
"""
import hmac
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.member_verification import (
    MemberVerification,
    QualificationResult,
    VerificationMethod,
)
from app.models.user import User
from app.services import verification as vsvc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/verification", tags=["verification"])


class WebhookPayload(BaseModel):
    reference: str
    check: str  # "identity" | "financial"
    outcome: str  # "passed" | "failed"
    method: VerificationMethod | None = None


async def _get_or_create(user: User, db: AsyncSession) -> MemberVerification:
    record = (
        await db.execute(
            select(MemberVerification).where(MemberVerification.user_id == user.id)
        )
    ).scalar_one_or_none()
    if record is None:
        record = MemberVerification(user_id=user.id)
        db.add(record)
        await db.commit()
        await db.refresh(record)
    return record


@router.get("/me")
async def my_verification(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The member's own view — status and next step, still no stored amounts."""
    record = await _get_or_create(user, db)

    declared_income = getattr(user.profile, "income_range", None) if user.profile else None
    declared_net_worth = getattr(user.profile, "net_worth_range", None) if user.profile else None
    likely, basis = vsvc.evaluate_qualification(declared_income, declared_net_worth)

    return {
        "identity_verified": record.identity_verified,
        "identity_verified_at": record.identity_verified_at,
        "financially_verified": record.financially_verified_now,
        "financial_verified_at": record.financial_verified_at,
        "financial_verification_method": (
            record.financial_verification_method.value
            if record.financial_verification_method
            else None
        ),
        "qualification_result": record.qualification_result.value,
        "expires_at": record.verification_expires_at,
        "is_expired": record.is_expired,
        # Based on what they've declared, before any check is run. Shown only
        # to the member themselves so they know whether it's worth starting.
        "declared_qualifies": likely == QualificationResult.QUALIFIED,
        "declared_basis": basis.value if basis else None,
        "provider_configured": vsvc.provider_configured(),
    }


@router.post("/identity/start")
async def start_identity(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_or_create(user, db)
    if record.identity_verified:
        return {"status": "already_verified"}

    try:
        session = await vsvc.start_identity_check(user.id)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if session.get("reference"):
        record.identity_reference = session["reference"]
        await db.commit()
    return session


@router.post("/financial/start")
async def start_financial(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Identity first — a financial check attached to an unverified identity
    proves only that some account holds the assets, not that this member does."""
    record = await _get_or_create(user, db)
    if not record.identity_verified:
        raise HTTPException(
            status_code=400, detail="Verify your identity before financial eligibility."
        )
    if record.financially_verified_now:
        return {"status": "already_verified"}

    try:
        session = await vsvc.start_financial_check(user.id)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if session.get("reference"):
        record.financial_reference = session["reference"]
        await db.commit()
    return session


@router.post("/webhook")
async def provider_webhook(
    payload: WebhookPayload,
    request: Request,
    x_signature: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Provider callback carrying an outcome — never documents or amounts."""
    if not settings.VERIFICATION_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")
    if not hmac.compare_digest(x_signature, settings.VERIFICATION_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Bad signature")

    column = (
        MemberVerification.identity_reference
        if payload.check == "identity"
        else MemberVerification.financial_reference
    )
    record = (
        await db.execute(select(MemberVerification).where(column == payload.reference))
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Unknown reference")

    passed = payload.outcome == "passed"
    now = datetime.utcnow()

    if payload.check == "identity":
        record.identity_verified = passed
        record.identity_verified_at = now if passed else None
    else:
        record.financially_verified = passed
        record.financial_verified_at = now if passed else None
        record.financial_verification_method = payload.method if passed else None
        record.qualification_result = (
            QualificationResult.QUALIFIED if passed else QualificationResult.NOT_QUALIFIED
        )
        record.verification_expires_at = vsvc.expiry_from_now() if passed else None

    await db.commit()
    logger.info("verification %s for user %s: %s", payload.check, record.user_id, payload.outcome)
    return {"ok": True}
