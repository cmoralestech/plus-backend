"""Financial qualification and the verification provider boundary.

Two responsibilities, kept apart:

1. Deciding whether a member's declared standing clears the bar. Thresholds
   live in config so the bar can move without a release.
2. Talking to whoever performs the actual checks. PLUS never sees the
   documents — it receives an outcome and stores that.

With no provider configured, checks are recorded as pending. Nothing is
fabricated: an unverified member is never shown as verified.
"""
import logging
from datetime import datetime, timedelta

from app.config import settings
from app.models.member_verification import (
    MemberVerification,
    QualificationResult,
    VerificationMethod,
)
from app.models.profile import IncomeRange, NetWorthRange

logger = logging.getLogger(__name__)

# Floor of each band in USD. Compared against the configured threshold, so a
# member is judged on the least their band could mean, never the most.
INCOME_FLOOR = {
    IncomeRange.UNDER_100K: 0,
    IncomeRange.R100K_250K: 100_000,
    IncomeRange.R250K_500K: 250_000,
    IncomeRange.R500K_1M: 500_000,
    IncomeRange.R1M_5M: 1_000_000,
    IncomeRange.R5M_10M: 5_000_000,
    IncomeRange.OVER_10M: 10_000_000,
}

NET_WORTH_FLOOR = {
    NetWorthRange.UNDER_1M: 0,
    NetWorthRange.R1M_5M: 1_000_000,
    NetWorthRange.R5M_10M: 5_000_000,
    NetWorthRange.R10M_50M: 10_000_000,
    NetWorthRange.R50M_100M: 50_000_000,
    NetWorthRange.OVER_100M: 100_000_000,
}


def _floor(mapping: dict, value) -> int | None:
    if value is None:
        return None
    try:
        return mapping[value]
    except KeyError:
        # Unknown band: treat as unknown rather than as zero, so a new enum
        # value can't silently disqualify someone.
        logger.warning("unmapped verification band: %r", value)
        return None


def evaluate_qualification(
    income_range: IncomeRange | None,
    net_worth_range: NetWorthRange | None,
) -> tuple[QualificationResult, VerificationMethod | None]:
    """Whether declared standing clears the bar, and on which basis.

    Income is checked first only so the method reads sensibly; either alone is
    sufficient.
    """
    income_floor = _floor(INCOME_FLOOR, income_range)
    net_worth_floor = _floor(NET_WORTH_FLOOR, net_worth_range)

    if income_floor is None and net_worth_floor is None:
        return QualificationResult.PENDING, None

    if income_floor is not None and income_floor >= settings.VERIFICATION_MIN_INCOME_USD:
        return QualificationResult.QUALIFIED, VerificationMethod.INCOME

    if (
        net_worth_floor is not None
        and net_worth_floor >= settings.VERIFICATION_MIN_NET_WORTH_USD
    ):
        return QualificationResult.QUALIFIED, VerificationMethod.ASSETS

    return QualificationResult.NOT_QUALIFIED, None


def expiry_from_now() -> datetime:
    return datetime.utcnow() + timedelta(days=settings.VERIFICATION_VALIDITY_DAYS)


def provider_configured() -> bool:
    return bool(settings.VERIFICATION_PROVIDER and settings.VERIFICATION_PROVIDER_API_KEY)


async def start_identity_check(user_id: int) -> dict:
    """Open an identity session with the provider.

    Returns a dict with `reference` and optionally `redirect_url`. When no
    provider is configured this reports unavailability rather than pretending
    a check happened.
    """
    if not provider_configured():
        return {
            "status": "unavailable",
            "reason": "No verification provider is configured.",
            "reference": None,
            "redirect_url": None,
        }

    # Provider-specific session creation goes here. Deliberately left to the
    # integration rather than guessed at, since the request shape differs per
    # vendor and a wrong guess would look like working code.
    raise NotImplementedError(
        f"Identity checks for provider {settings.VERIFICATION_PROVIDER!r} are not implemented yet."
    )


async def start_financial_check(user_id: int) -> dict:
    if not provider_configured():
        return {
            "status": "unavailable",
            "reason": "No verification provider is configured.",
            "reference": None,
            "redirect_url": None,
        }

    raise NotImplementedError(
        f"Financial checks for provider {settings.VERIFICATION_PROVIDER!r} are not implemented yet."
    )


def public_badges(record: MemberVerification | None) -> dict:
    """What other members are allowed to see.

    Only whether each check passed. Never an amount, a band, a document, or
    which basis qualified them.
    """
    if record is None:
        return {"identity_verified": False, "financially_verified": False}
    return {
        "identity_verified": bool(record.identity_verified),
        "financially_verified": record.financially_verified_now,
    }
