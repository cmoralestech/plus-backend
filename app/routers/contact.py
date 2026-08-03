import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.contact import ContactSubmission
from app.services.email import send_contact_form, send_contact_confirmation

logger = logging.getLogger("plus.contact")

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/contact", tags=["contact"])

VALID_CATEGORIES = [
    "general",
    "account",
    "billing",
    "safety",
    "bug",
    "press",
    "partnership",
    "other",
]

CATEGORY_LABELS = {
    "general": "General Question",
    "account": "Account Issue",
    "billing": "Billing & Subscription",
    "safety": "Safety Concern",
    "bug": "Bug Report",
    "press": "Press Inquiry",
    "partnership": "Partnership",
    "other": "Other",
}


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    category: str
    message: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Name is required")
        if len(v) > 100:
            raise ValueError("Name must be under 100 characters")
        return v

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(VALID_CATEGORIES)}")
        return v

    @field_validator("message")
    @classmethod
    def message_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 20:
            raise ValueError("Message must be at least 20 characters")
        if len(v) > 5000:
            raise ValueError("Message must be under 5000 characters")
        return v


@router.post("")
@limiter.limit("3/hour")
async def submit_contact(
    request: Request,
    data: ContactRequest,
    db: AsyncSession = Depends(get_db),
):
    label = CATEGORY_LABELS.get(data.category, data.category)

    # Persist first. We promise the sender a reply, so the message has to
    # survive anything that happens to email afterwards.
    submission = ContactSubmission(
        name=data.name,
        email=data.email,
        category=label,
        message=data.message,
    )
    db.add(submission)
    await db.flush()

    try:
        # send_contact_form reports success by return value, not by raising —
        # it must not raise, or a mail outage would fail the request. Trusting
        # "it didn't throw" would mark every submission notified even with no
        # mail provider configured at all.
        submission.notified = bool(
            send_contact_form(
                name=data.name,
                email=data.email,
                category=label,
                message=data.message,
            )
        )
    except Exception:
        logger.exception("[CONTACT] Notification failed for submission %s", submission.id)
        submission.notified = False

    if not submission.notified:
        logger.error(
            "[CONTACT] Submission %s stored but not delivered — admin queue is the only copy",
            submission.id,
        )

    await db.commit()

    try:
        send_contact_confirmation(to=data.email, name=data.name)
        from app.services.audience import add_contact
        add_contact(email=data.email, first_name=data.name, source="contact_form")
    except Exception:
        logger.exception("[CONTACT] Confirmation/audience step failed")

    return {"message": "Your message has been sent. We'll get back to you within 24 hours."}
