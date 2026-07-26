from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.email import send_contact_form, send_contact_confirmation

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
async def submit_contact(request: Request, data: ContactRequest):
    label = CATEGORY_LABELS.get(data.category, data.category)
    send_contact_form(
        name=data.name,
        email=data.email,
        category=label,
        message=data.message,
    )
    send_contact_confirmation(to=data.email, name=data.name)
    # Add to email audience
    from app.services.audience import add_contact
    add_contact(email=data.email, first_name=data.name, source="contact_form")
    return {"message": "Your message has been sent. We'll get back to you within 24 hours."}
