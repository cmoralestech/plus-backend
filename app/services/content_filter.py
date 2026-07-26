"""Content filter for FOSTA/SESTA compliance.

Scans text for high-confidence escort/prostitution/trafficking terminology.
Does NOT flag normal sugar dating vocabulary (arrangement, allowance, generous, etc.).
"""
import re

# High-confidence terms — almost always indicate prohibited activity in a dating context
FLAGGED_TERMS = [
    # Escort/prostitution terminology
    "escort service", "escort agency", "full service", "full svc",
    "incall", "outcall", "in-call", "out-call",
    "pay for sex", "sex for money", "sex for cash",
    "happy ending", "happy endings",
    "hourly rate", "per hour rate",
    # Escort abbreviations
    "GFE", "PSE", "BBBJ", "MSOG", "CIM", "COF", "DFK",
    "bare back", "bareback",
    # Explicit solicitation
    "prostitute", "prostitution", "prostituting", "hooker", "call girl", "streetwalker",
    "sex worker", "sex work",
    "soliciting sex", "solicit sex",
    "buy sex", "sell sex", "selling sex",
    "commercial sex",
    # Payment slang in escort context
    "roses per hour", "roses for",
    "donation required", "donations accepted",
    # Trafficking indicators
    "underage", "under age", "barely legal",
    "young girl", "young boy",
    "fresh meat", "fresh off the boat",
    "owned by", "belongs to me",
    "i control", "my girls",
    "work for me", "work the streets",
]

# Compile a single regex pattern for efficient matching
_pattern = re.compile(
    r'\b(' + '|'.join(re.escape(term) for term in FLAGGED_TERMS) + r')\b',
    re.IGNORECASE,
)


def scan_text(text: str) -> tuple[bool, str | None]:
    """Scan text for prohibited content.

    Returns (is_flagged, matched_term).
    """
    if not text:
        return False, None
    match = _pattern.search(text)
    if match:
        return True, match.group(0).lower()
    return False, None
