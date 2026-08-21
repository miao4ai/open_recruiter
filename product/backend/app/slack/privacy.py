"""Stage 3: Strip sensitive PII before storage.

Removes SSN, date-of-birth, passport numbers, and driver's license numbers.
Does NOT remove name, email, or phone — those are required for recruitment.
"""

from __future__ import annotations

import re

REDACTION = "[REDACTED]"

# Social Security Number: 123-45-6789 or 123 45 6789
_SSN = re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b")

# Date-of-birth patterns
_DOB_LABEL = re.compile(
    r"(?:DOB|date\s+of\s+birth|born|birthday)\s*[:=]?\s*\S+(?:\s+\S+){0,2}",
    re.IGNORECASE,
)
_DOB_DATE = re.compile(
    r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b"
)

# Passport number (labeled)
_PASSPORT = re.compile(
    r"(?:passport\s*(?:no|number|#)?)\s*[:=]?\s*[A-Z0-9]{6,9}", re.IGNORECASE
)

# Driver's license (labeled)
_DRIVERS_LICENSE = re.compile(
    r"(?:driver.?s?\s*licen[sc]e\s*(?:no|number|#)?)\s*[:=]?\s*[A-Z0-9\-]{5,15}",
    re.IGNORECASE,
)

_ALL_PATTERNS = [_SSN, _DOB_LABEL, _DOB_DATE, _PASSPORT, _DRIVERS_LICENSE]


def filter_pii(parsed: dict, raw_text: str) -> tuple[dict, str]:
    """Strip sensitive PII from parsed profile and raw text.

    Returns (cleaned_parsed, cleaned_text).
    """
    cleaned_text = _scrub(raw_text)

    cleaned = parsed.copy()
    if cleaned.get("resume_summary"):
        cleaned["resume_summary"] = _scrub(cleaned["resume_summary"])

    return cleaned, cleaned_text


def _scrub(text: str) -> str:
    for pattern in _ALL_PATTERNS:
        text = pattern.sub(REDACTION, text)
    return text
