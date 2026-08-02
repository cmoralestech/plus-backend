"""Funnel analytics: track user journey from signup to payment."""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.funnel import FunnelEvent
from app.models.user import User
from app.routers.admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

VALID_EVENTS = {
    "signup", "profile_created", "paywall_hit", "pricing_viewed",
    "subscription_tab_viewed", "checkout_started", "checkout_completed",
    "checkout_cancelled", "search_location", "newsletter_subscribe",
    "cancellation_saved", "subscription_cancelled", "profile_viewed",
}


class EventIn(BaseModel):
    event: str
    metadata: dict | None = None


@router.post("/event")
async def track_event(
    body: EventIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.event not in VALID_EVENTS:
        raise HTTPException(status_code=400, detail="Invalid event name")

    ev = FunnelEvent(
        user_id=user.id,
        user_type=user.user_type.value,
        event=body.event,
        metadata_=body.metadata,
    )
    db.add(ev)
    await db.commit()
    return {"tracked": True}


@router.get("/funnel")
async def get_funnel(
    days: int = 30,
    user_type: str = "established",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Conversion funnel for sugar daddies (or any user type).

    Returns event counts and per-user breakdown so you can see
    exactly where users drop off.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Aggregate counts per event
    result = await db.execute(
        select(FunnelEvent.event, func.count(func.distinct(FunnelEvent.user_id)))
        .where(FunnelEvent.created_at >= cutoff, FunnelEvent.user_type == user_type)
        .group_by(FunnelEvent.event)
    )
    counts = {row[0]: row[1] for row in result.all()}

    # Ordered funnel stages
    stages = [
        "signup", "profile_created", "paywall_hit", "pricing_viewed",
        "subscription_tab_viewed", "checkout_started", "checkout_completed",
    ]
    funnel = []
    for stage in stages:
        count = counts.get(stage, 0)
        funnel.append({"stage": stage, "users": count})

    # Per-user journey: which stages each user reached
    result = await db.execute(
        select(
            FunnelEvent.user_id,
            func.array_agg(func.distinct(FunnelEvent.event)),
        )
        .where(FunnelEvent.created_at >= cutoff, FunnelEvent.user_type == user_type)
        .group_by(FunnelEvent.user_id)
    )
    user_journeys = []
    for row in result.all():
        uid, events = row
        furthest = "signup"
        for s in stages:
            if s in events:
                furthest = s
        user_journeys.append({
            "user_id": uid,
            "events": events,
            "furthest_stage": furthest,
        })

    # Sort by furthest stage reached (deepest first)
    stage_order = {s: i for i, s in enumerate(stages)}
    user_journeys.sort(key=lambda x: stage_order.get(x["furthest_stage"], 0), reverse=True)

    return {
        "days": days,
        "user_type": user_type,
        "funnel": funnel,
        "user_journeys": user_journeys[:50],
        "checkout_cancelled": counts.get("checkout_cancelled", 0),
    }


@router.get("/locations")
async def get_location_demand(
    days: int = 30,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Where users are searching for companions — city-level demand heatmap."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            FunnelEvent.metadata_["city"].as_string().label("city"),
            func.count().label("searches"),
            func.count(func.distinct(FunnelEvent.user_id)).label("unique_users"),
        )
        .where(
            FunnelEvent.event == "search_location",
            FunnelEvent.created_at >= cutoff,
        )
        .group_by("city")
        .order_by(func.count().desc())
        .limit(50)
    )
    rows = result.all()

    return {
        "days": days,
        "locations": [
            {"city": r.city, "searches": r.searches, "unique_users": r.unique_users}
            for r in rows
            if r.city
        ],
    }
