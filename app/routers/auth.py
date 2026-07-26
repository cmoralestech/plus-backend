import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.config import settings

limiter = Limiter(key_func=get_remote_address)
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token, PasswordResetRequest, PasswordResetConfirm
from app.services.auth import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, verify_refresh_token,
    create_reset_token, verify_reset_token, verify_reset_token_hash,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

IS_PROD = settings.ENVIRONMENT == "production"


def _set_refresh_cookie(response: Response, refresh_token: str):
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response):
    response.delete_cookie(key="refresh_token", path="/api/auth")


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        user_type=user.user_type,
        is_verified=user.is_verified,
        created_at=user.created_at,
        has_profile=user.profile is not None,
    )


def _post_registration_tasks(user_id: int, email: str, user_type_value: str):
    """Run Stripe, email, and audience tasks in a background thread (sync I/O)."""
    # Create Stripe customer and update subscription record
    try:
        import stripe
        from sqlalchemy import update as sa_update
        from app.models.subscription import Subscription as SubModel
        stripe.api_key = settings.STRIPE_SECRET_KEY
        if stripe.api_key:
            customer = stripe.Customer.create(
                email=email,
                metadata={"user_id": str(user_id), "user_type": user_type_value},
            )
            # Update the subscription record with the Stripe customer ID (sync DB)
            from sqlalchemy import create_engine
            from sqlalchemy.orm import Session as SyncSession
            sync_engine = create_engine(settings.DATABASE_URL_SYNC)
            with SyncSession(sync_engine) as session:
                session.execute(
                    sa_update(SubModel)
                    .where(SubModel.user_id == user_id)
                    .values(stripe_customer_id=customer.id)
                )
                session.commit()
            sync_engine.dispose()
            logger.info(f"[STRIPE] Created customer {customer.id} for user {user_id}")
    except Exception as e:
        logger.error(f"[STRIPE] Failed for user {user_id}: {e}", exc_info=True)

    # Send verification email + notify admin + add to audience
    try:
        from app.services.auth import create_email_verification_token
        from app.services.email import send_email_verification, send_admin_new_user
        from app.services.audience import add_contact
        verify_token = create_email_verification_token(user_id)
        send_email_verification(email, verify_token)
        send_admin_new_user(email, user_type_value)
        add_contact(email=email, user_type=user_type_value, source="signup")
    except Exception as e:
        logger.error(f"[SIGNUP] Post-registration tasks failed for user {user_id}: {e}", exc_info=True)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(
    request: Request,
    data: UserCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Validate age if date_of_birth provided
    if data.date_of_birth:
        from datetime import date
        today = date.today()
        age = today.year - data.date_of_birth.year - (
            (today.month, today.day) < (data.date_of_birth.month, data.date_of_birth.day)
        )
        if age < 18:
            raise HTTPException(status_code=400, detail="You must be at least 18 years old to join Plus.")

    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        user_type=data.user_type,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    await db.refresh(user)

    # Create subscription record (Stripe customer ID filled in by background task)
    try:
        from app.models.subscription import Subscription
        sub = Subscription(user_id=user.id)
        db.add(sub)
        await db.commit()
    except Exception as e:
        logger.error(f"[STRIPE] Sub record failed for user {user.id}: {e}", exc_info=True)

    # Track signup in funnel
    from app.models.funnel import FunnelEvent
    signup_meta = {}
    if data.referrer:
        signup_meta["referrer"] = data.referrer
    if data.landing_page:
        signup_meta["landing_page"] = data.landing_page
    if data.utm_source:
        signup_meta["utm_source"] = data.utm_source
    if data.utm_medium:
        signup_meta["utm_medium"] = data.utm_medium
    if data.utm_campaign:
        signup_meta["utm_campaign"] = data.utm_campaign
    if data.utm_content:
        signup_meta["utm_content"] = data.utm_content
    db.add(FunnelEvent(user_id=user.id, user_type=data.user_type.value, event="signup", metadata_=signup_meta or None))
    await db.commit()

    # Sync HTTP calls (Stripe API, Resend, etc.) run in background thread
    background_tasks.add_task(
        _post_registration_tasks, user.id, data.email, data.user_type.value
    )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return Token(access_token=access_token, user=_user_response(user))


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    from app.services.lockout import is_locked_out, record_failed_attempt, clear_attempts, lockout_remaining_seconds

    if is_locked_out(data.email):
        remaining = lockout_remaining_seconds(data.email)
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked. Try again in {remaining // 60 + 1} minutes.",
        )

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        record_failed_attempt(data.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    clear_attempts(data.email)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return Token(access_token=access_token, user=_user_response(user))


@router.post("/refresh", response_model=Token)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    user_id = verify_refresh_token(token)
    if not user_id:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    _set_refresh_cookie(response, new_refresh)

    return Token(access_token=access_token, user=_user_response(user))


@router.post("/logout")
async def logout(response: Response):
    _clear_refresh_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from datetime import datetime
    user.last_seen = datetime.utcnow()
    await db.commit()
    return _user_response(user)


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    from app.services.auth import verify_email_token
    user_id = verify_email_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified", "already_verified": True}

    user.is_verified = True
    await db.commit()
    return {"message": "Email verified successfully", "verified": True}


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.is_verified:
        return {"message": "Already verified"}

    try:
        from app.services.auth import create_email_verification_token
        from app.services.email import send_email_verification
        token = create_email_verification_token(user.id)
        send_email_verification(user.email, token)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send verification email")

    return {"message": "Verification email sent"}


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(request: Request, data: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user:
        token = create_reset_token(user.id, user.password_hash)
        from app.services.email import send_password_reset
        send_password_reset(user.email, token)
    # Always return same response to prevent email enumeration
    return {"message": "If an account exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(data: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    user_id = verify_reset_token(data.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")

    # Verify token hasn't already been used (password unchanged since issuance)
    if not verify_reset_token_hash(data.token, user.password_hash):
        raise HTTPException(status_code=400, detail="This reset link has already been used")

    user.password_hash = hash_password(data.new_password)
    await db.commit()
    return {"message": "Password reset successfully"}
