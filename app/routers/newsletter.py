"""Newsletter subscription endpoint for blog/site visitors."""
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.audience import add_contact, remove_contact
from app.services.email import send_newsletter_welcome

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


class SubscribeRequest(BaseModel):
    email: EmailStr
    source: str = "blog"


@router.post("/subscribe")
@limiter.limit("5/hour")
async def subscribe(
    request: Request,
    data: SubscribeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    add_contact(email=data.email, source=data.source)

    # Store subscription for drip scheduling
    from app.models.funnel import FunnelEvent
    db.add(FunnelEvent(
        event="newsletter_subscribe",
        metadata_={"email": data.email, "source": data.source},
    ))
    await db.commit()

    # Send welcome drip immediately in background
    background_tasks.add_task(send_newsletter_welcome, data.email)

    return {"subscribed": True}


@router.get("/unsubscribe")
@limiter.limit("10/hour")
async def unsubscribe(request: Request, email: str = ""):
    """Remove an email from the Resend audience and show confirmation page."""
    from fastapi.responses import HTMLResponse

    if email:
        remove_contact(email)

    html_content = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Unsubscribed | Plus</title>
<style>body{margin:0;padding:0;background:#141210;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;color:#ede6db;}
.box{text-align:center;max-width:400px;padding:40px 20px;}
h1{font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;}
p{font-size:14px;color:#a8a090;line-height:1.7;margin:0;}</style>
</head>
<body><div class="box"><h1>You've been unsubscribed</h1><p>You will no longer receive marketing emails from Plus. If this was a mistake, you can re-subscribe from the blog at any time.</p></div></body>
</html>"""
    return HTMLResponse(content=html_content)


@router.post("/drip")
@limiter.limit("2/hour")
async def run_drip_emails(request: Request, db: AsyncSession = Depends(get_db)):
    """Process newsletter drip emails. Call daily via cron/GitHub Action.

    Day 3: comparison email. Day 7: final CTA email.
    """
    import logging
    from datetime import datetime, timedelta
    from app.models.funnel import FunnelEvent
    from app.services.email import send_newsletter_drip_comparison, send_newsletter_drip_cta

    logger = logging.getLogger(__name__)
    now = datetime.utcnow()

    # Find subscribers from 3 days ago (±12h window) who haven't gotten drip 2
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

    # Find subscribers from 7 days ago (±12h window) who haven't gotten drip 3
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
