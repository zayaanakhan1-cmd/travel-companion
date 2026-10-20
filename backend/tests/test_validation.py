"""Tests for input validation.

These matter because identifiers flow into both an outbound HTTP request and a
SQL query, so anything that is not strictly shaped must be rejected up front.
"""

from __future__ import annotations

import pytest

from app.errors import InvalidCountryCodeError, InvalidStateCodeError
from app.geography.validation import normalize_country_code, normalize_state_code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("in", "IN"), ("IN", "IN"), ("  us  ", "US"), ("gb", "GB")],
)
def test_country_code_is_normalised(raw: str, expected: str) -> None:
    assert normalize_country_code(raw) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "I",
        "IND",          # alpha-3 is not what the endpoints take
        "1N",
        "I1",
        "I N",
        "I;N",
        "IN'",
        "' OR '1'='1",
        "IN--",
        "<script>",
        "..%2f",
        "I\tN",
        "I.N",
    ],
)
def test_invalid_country_codes_are_rejected(bad: str) -> None:
    with pytest.raises(InvalidCountryCodeError):
        normalize_country_code(bad)


@pytest.mark.parametrize("raw", ["in\n", "  in  ", "\tin"])
def test_surrounding_whitespace_is_tolerated(raw: str) -> None:
    """Whitespace is stripped before matching, so it cannot smuggle a payload."""
    assert normalize_country_code(raw) == "IN"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("mh", "MH"), ("MH", "MH"), (" on ", "ON"), ("bds", "BDS"), ("A1", "A1")],
)
def test_state_code_is_normalised(raw: str, expected: str) -> None:
    assert normalize_state_code(raw) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "TOOLONG7",       # 7 chars
        "M H",
        "MH'",
        "' OR 1=1--",
        "MH;DROP",
        "../../etc",
        "<x>",
        "MH-",
    ],
)
def test_invalid_state_codes_are_rejected(bad: str) -> None:
    with pytest.raises(InvalidStateCodeError):
        normalize_state_code(bad)
