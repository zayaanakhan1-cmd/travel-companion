"""Shared test fixtures.

The geography tests run against a small, real SQLite cache built from an
inline fixture shaped exactly like the upstream dataset. Nothing is mocked:
the open-dataset provider executes genuine SQL against a genuine database.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

# A miniature but structurally faithful slice of the upstream dataset.
FIXTURE_COUNTRIES = [
    {
        "id": 101,
        "name": "India",
        "iso2": "IN",
        "iso3": "IND",
        "phonecode": "91",
        "capital": "New Delhi",
        "currency": "INR",
        "native": "भारत",
        "region": "Asia",
        "subregion": "Southern Asia",
        "latitude": "20.00000000",
        "longitude": "77.00000000",
        "emoji": "🇮🇳",
        "states": [
            {
                "id": 4008,
                "name": "Maharashtra",
                "iso2": "MH",
                "type": "state",
                "latitude": "19.75147980",
                "longitude": "75.71388840",
                "timezone": "Asia/Kolkata",
                "cities": [
                    {
                        "id": 133024,
                        "name": "Mumbai",
                        "latitude": "19.07283000",
                        "longitude": "72.88261000",
                        "timezone": "Asia/Kolkata",
                    },
                    {
                        "id": 133025,
                        "name": "Pune",
                        "latitude": "18.51957000",
                        "longitude": "73.85535000",
                        "timezone": "Asia/Kolkata",
                    },
                ],
            },
            {
                "id": 4009,
                "name": "Goa",
                "iso2": "GA",
                "type": "state",
                "latitude": "15.29932650",
                "longitude": "74.12399600",
                "timezone": "Asia/Kolkata",
                "cities": [],
            },
        ],
    },
    {
        "id": 39,
        "name": "Canada",
        "iso2": "CA",
        "iso3": "CAN",
        "phonecode": "1",
        "capital": "Ottawa",
        "currency": "CAD",
        "native": "Canada",
        "region": "Americas",
        "subregion": "Northern America",
        "latitude": "60.00000000",
        "longitude": "-95.00000000",
        "emoji": "🇨🇦",
        "states": [
            {
                "id": 872,
                "name": "Ontario",
                "iso2": "ON",
                "type": "province",
                "latitude": "51.25377500",
                "longitude": "-85.32321400",
                "timezone": "America/Toronto",
                "cities": [
                    {
                        "id": 1,
                        "name": "Toronto",
                        "latitude": "43.70011000",
                        "longitude": "-79.41630000",
                        "timezone": "America/Toronto",
                    }
                ],
            }
        ],
    },
]


@pytest.fixture
def dataset_payload_bytes() -> bytes:
    """The fixture dataset, gzip-compressed exactly like the real release."""
    return gzip.compress(json.dumps(FIXTURE_COUNTRIES).encode("utf-8"))


@pytest.fixture
def cache_path(tmp_path: Path) -> Path:
    """Destination for a per-test SQLite cache."""
    return tmp_path / "csc.sqlite3"


@pytest.fixture
def built_cache(cache_path: Path, dataset_payload_bytes: bytes) -> Path:
    """A real SQLite cache built from the fixture, via the production builder."""
    from app.geography.dataset_builder import build_cache

    return build_cache(
        url="https://example.invalid/dataset.json.gz",
        destination=cache_path,
        raw_bytes=dataset_payload_bytes,
    )
