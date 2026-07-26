"""Account lockout after failed login attempts."""
from datetime import datetime, timedelta
from collections import defaultdict

# In-memory store (for single instance). For multi-instance, use Redis.
_failed_attempts: dict[str, list[datetime]] = defaultdict(list)

MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
WINDOW_MINUTES = 15


def record_failed_attempt(email: str):
    now = datetime.utcnow()
    _failed_attempts[email].append(now)
    # Prune old entries
    cutoff = now - timedelta(minutes=WINDOW_MINUTES)
    _failed_attempts[email] = [t for t in _failed_attempts[email] if t > cutoff]


def is_locked_out(email: str) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=WINDOW_MINUTES)
    recent = [t for t in _failed_attempts.get(email, []) if t > cutoff]
    return len(recent) >= MAX_ATTEMPTS


def clear_attempts(email: str):
    _failed_attempts.pop(email, None)


def lockout_remaining_seconds(email: str) -> int:
    attempts = _failed_attempts.get(email, [])
    if not attempts or not is_locked_out(email):
        return 0
    oldest_relevant = attempts[-MAX_ATTEMPTS]
    unlock_at = oldest_relevant + timedelta(minutes=LOCKOUT_MINUTES)
    remaining = (unlock_at - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))
