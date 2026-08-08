"""Push delivery via Expo's push service.

Expo fronts APNs, so no Apple certificate lives here — but delivery still
requires push credentials configured against the app's bundle identifier in
EAS. Until that exists, every send is accepted by this module and dropped by
Expo. That is logged plainly rather than reported as a success, because a
notification system that silently does nothing is worse than one that is off.
"""
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import DeviceToken

logger = logging.getLogger("plus.push")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
# Expo's documented cap per request.
BATCH_SIZE = 100
TIMEOUT_SECONDS = 10.0


async def send_push(
    db: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    data: dict | None = None,
) -> int:
    """Deliver to every active device for a member. Returns tickets accepted.

    Never raises: a failed notification must not roll back the action that
    triggered it. Somebody's message is not lost because a push failed.
    """
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True,  # noqa: E712
        )
    )
    tokens = [d.token for d in result.scalars().all()]
    if not tokens:
        return 0

    messages = [
        {
            "to": token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
            # Collapse repeats of the same conversation rather than stacking.
            "channelId": "default",
        }
        for token in tokens
    ]

    accepted = 0
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            for start in range(0, len(messages), BATCH_SIZE):
                batch = messages[start : start + BATCH_SIZE]
                response = await client.post(
                    EXPO_PUSH_URL,
                    json=batch,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                if response.status_code != 200:
                    logger.error(
                        "[PUSH] Expo rejected a batch: %s %s",
                        response.status_code,
                        response.text[:300],
                    )
                    continue

                tickets = response.json().get("data", [])
                for token, ticket in zip((m["to"] for m in batch), tickets):
                    if ticket.get("status") == "ok":
                        accepted += 1
                        continue

                    detail = (ticket.get("details") or {}).get("error")
                    logger.warning("[PUSH] Ticket error for a device: %s", detail or ticket.get("message"))
                    if detail == "DeviceNotRegistered":
                        # The app was uninstalled or the token was revoked.
                        # Deactivate so we stop paying to send into a void.
                        await _deactivate(db, token)
    except Exception:
        logger.exception("[PUSH] Delivery failed for user_id=%s", user_id)
        return accepted

    return accepted


async def _deactivate(db: AsyncSession, token: str) -> None:
    result = await db.execute(select(DeviceToken).where(DeviceToken.token == token))
    device = result.scalar_one_or_none()
    if device:
        device.is_active = False
