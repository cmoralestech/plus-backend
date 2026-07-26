"""Resend Audience management — add contacts for email marketing."""
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com"


def add_contact(
    email: str,
    first_name: str = "",
    user_type: str = "",
    source: str = "signup",
):
    """Add or update a contact in the Resend audience."""
    api_key = settings.RESEND_API_KEY
    audience_id = settings.RESEND_AUDIENCE_ID
    if not api_key or not audience_id:
        logger.info("[AUDIENCE STUB] Would add %s (source=%s)", email, source)
        return

    try:
        resp = httpx.post(
            f"{RESEND_API}/audiences/{audience_id}/contacts",
            json={
                "email": email,
                "first_name": first_name or "",
                "unsubscribed": False,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info("[AUDIENCE] Added %s (source=%s)", email, source)
        else:
            logger.warning("[AUDIENCE] Failed to add %s: %s %s", email, resp.status_code, resp.text)
    except Exception as e:
        logger.warning("[AUDIENCE] Error adding %s: %s", email, e)


def remove_contact(email: str):
    """Remove a contact from the Resend audience (for account deletion)."""
    api_key = settings.RESEND_API_KEY
    audience_id = settings.RESEND_AUDIENCE_ID
    if not api_key or not audience_id:
        return

    try:
        # First get the contact ID by email
        resp = httpx.get(
            f"{RESEND_API}/audiences/{audience_id}/contacts",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            contacts = resp.json().get("data", [])
            for c in contacts:
                if c.get("email") == email:
                    httpx.delete(
                        f"{RESEND_API}/audiences/{audience_id}/contacts/{c['id']}",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10,
                    )
                    logger.info("[AUDIENCE] Removed %s", email)
                    break
    except Exception as e:
        logger.warning("[AUDIENCE] Error removing %s: %s", email, e)
