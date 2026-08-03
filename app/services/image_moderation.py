"""Automated screening of uploaded photographs.

The text filter in ``content_filter`` catches what people write. This catches
what they upload — the gap payment processors and app stores ask about.

Inert until ``IMAGE_MODERATION_PROVIDER`` is set, so the platform runs unchanged
without credentials. When a provider is configured, every upload is screened
before it becomes visible and lands in one of three outcomes:

    REJECT  the upload is refused and the bytes are never stored
    FLAG    stored but hidden from discovery until a human reviews it
    PASS    visible immediately

A scan that fails for any reason (provider down, image too large to process,
credentials wrong) returns ERROR. With ``IMAGE_MODERATION_FAIL_CLOSED`` — the
default — an errored upload is treated as FLAG rather than waved through, so an
outage degrades into a review backlog instead of a hole in the filter.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

from app.config import settings

logger = logging.getLogger("plus.moderation")

# Rekognition accepts at most 5 MB of image bytes inline. Anything larger is
# downscaled before the call rather than rejected — a 10 MB phone photo is
# ordinary, not suspicious.
_MAX_SCAN_BYTES = 5 * 1024 * 1024
_DOWNSCALE_TO = (2048, 2048)


class Action(str, Enum):
    PASS = "passed"
    FLAG = "flagged"
    REJECT = "rejected"
    ERROR = "error"
    UNSCANNED = "unscanned"


# Rekognition's moderation taxonomy changed names between v6 and v7 and the
# deployed version depends on region, so both spellings are mapped. Anything not
# listed is allowed: swimwear, underwear, alcohol and gambling are all ordinary
# content on a dating profile and flagging them would bury reviewers in noise.
_REJECT_CATEGORIES = {
    "explicit",
    "explicit nudity",
    "sexual activity",
    "graphic violence",
    "violence",
    "visually disturbing",
    "hate symbols",
    "extremist",
}

_FLAG_CATEGORIES = {
    "non-explicit nudity of intimate parts and kissing",
    "non-explicit nudity",
    "suggestive",
    "drugs & tobacco",
    "drugs",
    "rude gestures",
    "self-harm",
}


@dataclass
class Verdict:
    action: Action
    provider: str = ""
    top_label: str | None = None
    top_confidence: float | None = None
    labels: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def reason(self) -> str | None:
        """Short human-readable reason, suitable for a flag_reason column."""
        if self.action == Action.ERROR:
            return f"Scan failed: {self.error}"[:200]
        if self.top_label:
            confidence = f" ({self.top_confidence:.0f}%)" if self.top_confidence else ""
            return f"{self.top_label}{confidence}"[:200]
        return None

    @property
    def blocks_upload(self) -> bool:
        return self.action == Action.REJECT

    @property
    def needs_review(self) -> bool:
        return self.action in (Action.FLAG, Action.ERROR)


def is_enabled() -> bool:
    return bool(settings.IMAGE_MODERATION_PROVIDER)


def _classify(labels: list[dict]) -> Verdict:
    """Turn provider labels into an action.

    Rekognition returns both a top-level category and its specific child (e.g.
    parent "Explicit", name "Sexual Activity"). We judge on the parent where one
    is present so the category list stays short and stable across taxonomy
    revisions, and fall back to the label's own name for top-level hits.
    """
    reject_threshold = settings.IMAGE_MODERATION_REJECT_THRESHOLD
    flag_threshold = settings.IMAGE_MODERATION_FLAG_THRESHOLD

    worst = Action.PASS
    top_label: str | None = None
    top_confidence: float | None = None

    for label in labels:
        name = (label.get("Name") or "").strip()
        parent = (label.get("ParentName") or "").strip()
        confidence = float(label.get("Confidence") or 0.0)
        category = (parent or name).lower()

        if category in _REJECT_CATEGORIES and confidence >= reject_threshold:
            action = Action.REJECT
        elif (
            category in _REJECT_CATEGORIES or category in _FLAG_CATEGORIES
        ) and confidence >= flag_threshold:
            action = Action.FLAG
        else:
            continue

        # REJECT outranks FLAG; within the same action the most confident wins.
        outranks = action == Action.REJECT and worst != Action.REJECT
        same_rank_stronger = action == worst and confidence > (top_confidence or 0)
        if outranks or same_rank_stronger or worst == Action.PASS:
            worst = action
            top_label = name or parent
            top_confidence = confidence

    return Verdict(
        action=worst,
        provider=settings.IMAGE_MODERATION_PROVIDER,
        top_label=top_label,
        top_confidence=top_confidence,
        labels=[
            {
                "name": lbl.get("Name"),
                "parent": lbl.get("ParentName"),
                "confidence": round(float(lbl.get("Confidence") or 0.0), 2),
            }
            for lbl in labels
        ],
    )


def _shrink_for_scan(contents: bytes) -> bytes:
    """Downscale oversized images so they fit the provider's inline limit."""
    if len(contents) <= _MAX_SCAN_BYTES:
        return contents

    from PIL import Image

    with Image.open(io.BytesIO(contents)) as img:
        img = img.convert("RGB")
        img.thumbnail(_DOWNSCALE_TO)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()


def misconfiguration() -> str | None:
    """Why the configured provider cannot run, or None if it can.

    Object storage is Tigris, which publishes its credentials under the AWS_*
    names. boto3 would happily pick those up for Rekognition and fail
    authentication on every call — which, failing closed, would hold every
    upload on the platform. Catching it here turns a silent outage into a log
    line, and screening stays off rather than blocking members.
    """
    if not is_enabled():
        return None
    if settings.IMAGE_MODERATION_PROVIDER.lower() != "rekognition":
        return f"unknown provider {settings.IMAGE_MODERATION_PROVIDER!r}"
    if settings.IMAGE_MODERATION_ACCESS_KEY_ID:
        return None
    if os.environ.get("AWS_ENDPOINT_URL_S3"):
        return (
            "IMAGE_MODERATION_ACCESS_KEY_ID is unset and the ambient AWS_* "
            "credentials belong to a third-party S3 endpoint "
            f"({os.environ['AWS_ENDPOINT_URL_S3']}), which cannot authenticate "
            "against Rekognition. Set dedicated AWS credentials."
        )
    return None


@lru_cache(maxsize=1)
def _client():
    """Cached — constructing a boto3 client costs more than the scan it makes."""
    import boto3

    kwargs = {"region_name": settings.IMAGE_MODERATION_REGION or "us-east-1"}
    if settings.IMAGE_MODERATION_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.IMAGE_MODERATION_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.IMAGE_MODERATION_SECRET_ACCESS_KEY
    return boto3.client("rekognition", **kwargs)


def _scan_rekognition(contents: bytes) -> list[dict]:
    """Blocking Rekognition call — always invoked off the event loop."""
    response = _client().detect_moderation_labels(
        Image={"Bytes": _shrink_for_scan(contents)},
        # Ask for everything above the flag threshold and decide locally, so the
        # two thresholds stay tunable without a second round trip.
        MinConfidence=min(
            settings.IMAGE_MODERATION_FLAG_THRESHOLD,
            settings.IMAGE_MODERATION_REJECT_THRESHOLD,
        ),
    )
    return response.get("ModerationLabels", []) or []


async def scan_image(contents: bytes) -> Verdict:
    """Screen an uploaded image. Never raises — callers get a Verdict either way."""
    if not is_enabled():
        return Verdict(action=Action.UNSCANNED)

    # A misconfigured provider is not the same as a failed scan. Failing closed
    # is right when a working provider has a bad minute; applying it to a
    # permanent config error would hold every upload indefinitely and read to
    # members as a broken product. Be loud in the logs, leave uploads flowing.
    problem = misconfiguration()
    if problem:
        logger.error("[MODERATION] Screening disabled — %s", problem)
        return Verdict(action=Action.UNSCANNED, error=problem)

    provider = settings.IMAGE_MODERATION_PROVIDER.lower()

    try:
        labels = await asyncio.wait_for(
            asyncio.to_thread(_scan_rekognition, contents),
            timeout=settings.IMAGE_MODERATION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("[MODERATION] Scan timed out after %ss", settings.IMAGE_MODERATION_TIMEOUT_SECONDS)
        return Verdict(action=Action.ERROR, provider=provider, error="timeout")
    except Exception as exc:  # noqa: BLE001 — a scan failure must never 500 an upload
        logger.exception("[MODERATION] Scan failed")
        return Verdict(action=Action.ERROR, provider=provider, error=type(exc).__name__)

    verdict = _classify(labels)
    if verdict.action != Action.PASS:
        logger.info(
            "[MODERATION] %s — %s (%.0f%%)",
            verdict.action.value, verdict.top_label, verdict.top_confidence or 0,
        )
    return verdict


def resolve_outcome(verdict: Verdict) -> tuple[Action, bool, str | None]:
    """Collapse a verdict into what the upload handler should actually do.

    Returns (status_to_store, hide_pending_review, flag_reason). An ERROR becomes
    a FLAG when we are configured to fail closed, which is the point of the
    setting — an outage should not silently disable screening.
    """
    if verdict.action == Action.ERROR:
        if settings.IMAGE_MODERATION_FAIL_CLOSED:
            return Action.FLAG, True, verdict.reason
        # Failing open publishes the photo and keeps the error visible in
        # moderation_status, so the gap is auditable after the fact.
        return Action.ERROR, False, None
    return verdict.action, verdict.action == Action.FLAG, verdict.reason
