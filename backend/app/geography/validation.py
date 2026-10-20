"""Input validation for geography identifiers.

User-supplied path segments reach both an HTTP client and a SQL query, so they
are validated against a strict allow-list *before* either. Codes are ISO 3166-1
alpha-2 / ISO 3166-2 subdivision codes: ASCII letters and digits only.
"""

from __future__ import annotations

import re

from app.errors import InvalidCountryCodeError, InvalidStateCodeError

_COUNTRY_RE = re.compile(r"^[A-Za-z]{2}$")
# Subdivision codes vary: "MH" (India), "CA" (US state), "BDS" (Afghanistan),
# "ENG" (England). Letters/digits, up to 6 chars, is the practical envelope.
_STATE_RE = re.compile(r"^[A-Za-z0-9]{1,6}$")


def normalize_country_code(value: str) -> str:
    """Validate and upper-case an ISO 3166-1 alpha-2 country code."""
    candidate = (value or "").strip()
    if not _COUNTRY_RE.match(candidate):
        raise InvalidCountryCodeError(
            "Country code must be a two-letter ISO 3166-1 alpha-2 code, e.g. 'IN'.",
        )
    return candidate.upper()


def normalize_state_code(value: str) -> str:
    """Validate and upper-case a subdivision code."""
    candidate = (value or "").strip()
    if not _STATE_RE.match(candidate):
        raise InvalidStateCodeError(
            "State/region code must be 1-6 alphanumeric characters, e.g. 'MH'.",
        )
    return candidate.upper()
