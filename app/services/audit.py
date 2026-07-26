"""Audit logging service — records every modifiable action for legal defense."""
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    actor_type: str,
    actor_id: int | None = None,
    actor_email: str | None = None,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Log an auditable action. Call this from any endpoint that modifies data."""
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent", "")[:500]

    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(entry)
    # Don't commit — let the calling endpoint handle the transaction
    return entry
