"""Stripe billing: checkout, webhooks, portal."""
import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionTier
from app.models.funnel import FunnelEvent

logger = logging.getLogger(__name__)

# Idempotency: track processed webhook event IDs to prevent double-processing
_processed_events: set[str] = set()
_MAX_PROCESSED_EVENTS = 10000

router = APIRouter(prefix="/api/billing", tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY

TIER_TO_PRICE = {
    "plus": settings.STRIPE_PLUS_PRICE_ID,
    "plus_plus": settings.STRIPE_PLUS_PLUS_PRICE_ID,
    "plus_annual": settings.STRIPE_PLUS_ANNUAL_PRICE_ID,
    "plus_plus_annual": settings.STRIPE_PLUS_PLUS_ANNUAL_PRICE_ID,
}

# Map price IDs back to base tier names (strip _annual suffix)
PRICE_TO_TIER = {v: k.replace("_annual", "") for k, v in TIER_TO_PRICE.items() if v}


async def _get_or_create_sub(user_id: int, db: AsyncSession) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if not sub:
        sub = Subscription(user_id=user_id, tier=SubscriptionTier.FREE)
        db.add(sub)
        await db.flush()
    return sub


@router.post("/checkout")
async def create_checkout(
    tier: str,
    billing: str = "monthly",
    coupon: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for a subscription upgrade."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payments not configured")

    if tier not in ("plus", "plus_plus"):
        raise HTTPException(status_code=400, detail="Invalid tier. Use 'plus' or 'plus_plus'")

    if billing not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="Invalid billing. Use 'monthly' or 'annual'")

    price_key = f"{tier}_annual" if billing == "annual" else tier
    price_id = TIER_TO_PRICE[price_key]
    if not price_id:
        raise HTTPException(status_code=503, detail=f"Price not configured for {tier} ({billing})")

    sub = await _get_or_create_sub(user.id, db)

    # Create or retrieve Stripe customer — recreate if stale/missing
    if sub.stripe_customer_id:
        try:
            stripe.Customer.retrieve(sub.stripe_customer_id)
        except stripe.InvalidRequestError:
            logger.warning(f"[BILLING] Stale Stripe customer {sub.stripe_customer_id} for user {user.id}, creating new one")
            sub.stripe_customer_id = None

    if not sub.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.id)},
        )
        sub.stripe_customer_id = customer.id
        await db.commit()
        logger.info(f"[BILLING] Created Stripe customer {customer.id} for user {user.id}")

    session_params = {
        "customer": sub.stripe_customer_id,
        # payment_method_types is rejected while Managed Payments is on, and
        # required when it's off — so it follows the setting.
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{settings.FRONTEND_URL}/settings?tab=subscription&status=success",
        "cancel_url": f"{settings.FRONTEND_URL}/settings?tab=subscription&status=cancelled",
        "metadata": {"user_id": str(user.id), "tier": tier, "billing": billing},
    }
    if settings.STRIPE_MANAGED_PAYMENTS:
        # Stripe picks the methods, but every product needs a tax code set.
        pass
    else:
        session_params["managed_payments"] = {"enabled": False}
        session_params["payment_method_types"] = ["card"]

    if coupon:
        session_params["discounts"] = [{"coupon": coupon}]

    session = stripe.checkout.Session.create(**session_params)

    # Track checkout initiation
    db.add(FunnelEvent(user_id=user.id, user_type=user.user_type.value, event="checkout_started", metadata_={"tier": tier, "billing": billing}))
    await db.commit()

    return {"checkout_url": session.url}


@router.post("/verify-checkout")
async def verify_checkout(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify and activate subscription after returning from Stripe checkout.
    Called by the frontend when user returns with ?status=success."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payments not configured")

    sub = await _get_or_create_sub(user.id, db)
    if not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No checkout found")

    # Check Stripe for the customer's active subscriptions
    try:
        subscriptions = stripe.Subscription.list(
            customer=sub.stripe_customer_id,
            status="active",
            limit=1,
        )
        if subscriptions.data:
            stripe_sub = subscriptions.data[0]
            sub.stripe_subscription_id = stripe_sub.id
            sub.is_active = True

            # Determine tier from price
            items = stripe_sub.get("items", {}).get("data", [])
            if items:
                price_id = items[0].get("price", {}).get("id")
                tier_name = PRICE_TO_TIER.get(price_id)
                if tier_name:
                    sub.tier = SubscriptionTier(tier_name)

            from datetime import datetime
            sub.started_at = datetime.utcnow()
            # Track successful payment
            db.add(FunnelEvent(user_id=user.id, user_type=user.user_type.value, event="checkout_completed", metadata_={"tier": sub.tier.value}))
            await db.commit()
            return {"activated": True, "tier": sub.tier.value}

        return {"activated": False, "message": "No active subscription found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to verify: {str(e)}")


@router.post("/cancel")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel the user's subscription at the end of the current billing period."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payments not configured")

    sub = await _get_or_create_sub(user.id, db)

    if not sub.stripe_subscription_id or sub.tier == SubscriptionTier.FREE:
        raise HTTPException(status_code=400, detail="No active subscription to cancel")

    try:
        stripe_sub = stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        # Return the period end date so frontend can display it
        period_end = stripe_sub.get("current_period_end")
        from datetime import datetime
        period_end_dt = datetime.utcfromtimestamp(period_end) if period_end else None
        access_until = period_end_dt.strftime("%B %d, %Y") if period_end_dt else None

        return {
            "cancelled": True,
            "message": "Your subscription will be cancelled at the end of your billing period.",
            "access_until": access_until,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")


@router.post("/portal")
async def create_portal(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session for managing billing."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payments not configured")

    sub = await _get_or_create_sub(user.id, db)
    if not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active subscription")

    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/settings?tab=subscription",
    )

    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events for subscription lifecycle."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig, settings.STRIPE_WEBHOOK_SECRET
            )
        except (stripe.SignatureVerificationError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        # No signature verification — only allowed in dev/staging
        if "meetyourplus.com" in (settings.FRONTEND_URL or ""):
            raise HTTPException(
                status_code=403,
                detail="Webhook signature verification required in production",
            )
        logger.warning(
            "Webhook signature verification disabled — "
            "set STRIPE_WEBHOOK_SECRET in production"
        )
        import json
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)

    # Stripe SDK v15 returns StripeObject, not dict — use attribute access
    event_id = getattr(event, "id", "")
    if event_id in _processed_events:
        logger.info(f"[WEBHOOK] Skipping duplicate event {event_id}")
        return {"received": True, "duplicate": True}
    _processed_events.add(event_id)
    if len(_processed_events) > _MAX_PROCESSED_EVENTS:
        _processed_events.clear()

    event_type = getattr(event, "type", "")
    data = event.data.object
    logger.info(f"[WEBHOOK] Processing {event_type} (event={event_id})")

    if event_type == "checkout.session.completed":
        user_id = int(data.metadata["user_id"]) if hasattr(data, "metadata") and "user_id" in data.metadata else 0
        tier = data.metadata["tier"] if hasattr(data, "metadata") and "tier" in data.metadata else "plus"
        stripe_sub_id = getattr(data, "subscription", None)

        if user_id:
            result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
            sub = result.scalar_one_or_none()
            if sub:
                sub.tier = SubscriptionTier(tier)
                sub.stripe_subscription_id = stripe_sub_id
                sub.is_active = True
                from datetime import datetime
                sub.started_at = datetime.utcnow()
                await db.commit()
                logger.info(f"[WEBHOOK] Activated {tier} for user {user_id}")

                # Notify admin of new paid subscriber
                try:
                    from app.models.user import User as UserModel
                    from app.models.profile import Profile as ProfileModel
                    from app.services.email import send_admin_new_subscription, send_referral_prompt
                    from app.models.referral import ReferralLink, generate_referral_code
                    user_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
                    u = user_result.scalar_one_or_none()
                    profile_result = await db.execute(
                        select(ProfileModel).where(ProfileModel.user_id == user_id, ProfileModel.is_seed == False)
                    )
                    p = profile_result.scalar_one_or_none()
                    if u:
                        send_admin_new_subscription(
                            email=u.email,
                            display_name=p.display_name if p else "",
                            tier=tier,
                            city=p.city if p else "",
                        )
                        # Send referral prompt to the new subscriber
                        try:
                            ref_result = await db.execute(select(ReferralLink).where(ReferralLink.user_id == user_id))
                            ref_link = ref_result.scalar_one_or_none()
                            if not ref_link:
                                code = generate_referral_code()
                                ref_link = ReferralLink(user_id=user_id, code=code)
                                db.add(ref_link)
                                await db.commit()
                            send_referral_prompt(
                                to=u.email,
                                display_name=p.display_name if p else u.email.split("@")[0],
                                referral_code=ref_link.custom_slug or ref_link.code,
                            )
                        except Exception as ref_e:
                            logger.warning(f"[WEBHOOK] Referral prompt email failed: {ref_e}")
                except Exception as e:
                    logger.warning(f"[WEBHOOK] Admin notification failed: {e}")

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        stripe_sub_id = getattr(data, "id", None)
        status = getattr(data, "status", None)

        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            if status == "active":
                sub.is_active = True
                items_obj = getattr(data, "items", None)
                if items_obj and hasattr(items_obj, "data") and items_obj.data:
                    price_obj = getattr(items_obj.data[0], "price", None)
                    if price_obj:
                        price_id = getattr(price_obj, "id", None)
                        tier_name = PRICE_TO_TIER.get(price_id)
                        if tier_name:
                            sub.tier = SubscriptionTier(tier_name)
            elif status in ("canceled", "unpaid", "past_due"):
                sub.is_active = False
                if status == "canceled":
                    sub.tier = SubscriptionTier.FREE
            await db.commit()

    elif event_type == "invoice.payment_failed":
        customer_id = getattr(data, "customer", None)
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.is_active = False
            await db.commit()

    return {"received": True}
