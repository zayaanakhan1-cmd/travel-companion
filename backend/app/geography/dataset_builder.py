"""Builds a local SQLite cache from the open countries-states-cities dataset.

Source: https://github.com/dr5hn/countries-states-cities-database
Licence: ODbL-1.0 (attribution + share-alike for derived databases).

The upstream combined JSON is ~53 MB uncompressed. Rather than hold it in
memory at query time, we stream the release archive, project the fields the API
actually exposes, and write a compact SQLite file (~21 MB) with indexes. Query
time then needs no network and no quota.

The cache is generated data: it lives under `backend/data/` and is git-ignored.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sqlite3
import tempfile
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE countries (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    iso2 TEXT NOT NULL,
    iso3 TEXT,
    phonecode TEXT,
    capital TEXT,
    currency TEXT,
    native TEXT,
    region TEXT,
    subregion TEXT,
    latitude TEXT,
    longitude TEXT,
    emoji TEXT
);
CREATE TABLE states (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    iso2 TEXT,
    country_id INTEGER NOT NULL,
    country_code TEXT NOT NULL,
    type TEXT,
    latitude TEXT,
    longitude TEXT,
    timezone TEXT
);
CREATE TABLE cities (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    state_id INTEGER,
    country_id INTEGER NOT NULL,
    country_code TEXT NOT NULL,
    state_code TEXT,
    latitude TEXT,
    longitude TEXT,
    timezone TEXT
);
CREATE INDEX idx_countries_name ON countries(name);
CREATE INDEX idx_countries_iso2 ON countries(iso2);
CREATE INDEX idx_states_country_code ON states(country_code);
CREATE INDEX idx_states_iso2 ON states(country_code, iso2);
CREATE INDEX idx_cities_state ON cities(state_id);
CREATE INDEX idx_cities_country_code ON cities(country_code);
CREATE INDEX idx_cities_country_state ON cities(country_code, state_code);
CREATE INDEX idx_cities_name ON cities(name);
"""


def _download(url: str, timeout: float) -> bytes:
    """Download the dataset archive into memory (a few MB compressed)."""
    logger.info("Downloading open geography dataset")
    request = urllib.request.Request(url, headers={"User-Agent": "travel-companion"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def _read_payload(raw: bytes) -> list[dict]:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _insert_dataset(conn: sqlite3.Connection, countries: list[dict]) -> None:
    country_rows: list[tuple] = []
    state_rows: list[tuple] = []
    city_rows: list[tuple] = []

    for country in countries:
        country_code = country.get("iso2")
        if not country_code:
            continue
        country_rows.append(
            (
                country.get("id"),
                country.get("name") or "",
                country_code,
                country.get("iso3"),
                country.get("phonecode"),
                country.get("capital"),
                country.get("currency"),
                country.get("native"),
                country.get("region"),
                country.get("subregion"),
                country.get("latitude"),
                country.get("longitude"),
                country.get("emoji"),
            )
        )
        for state in country.get("states") or []:
            state_code = state.get("iso2")
            state_rows.append(
                (
                    state.get("id"),
                    state.get("name") or "",
                    state_code,
                    country.get("id"),
                    country_code,
                    state.get("type"),
                    state.get("latitude"),
                    state.get("longitude"),
                    state.get("timezone"),
                )
            )
            for city in state.get("cities") or []:
                city_rows.append(
                    (
                        city.get("id"),
                        city.get("name") or "",
                        state.get("id"),
                        country.get("id"),
                        country_code,
                        state_code,
                        city.get("latitude"),
                        city.get("longitude"),
                        city.get("timezone"),
                    )
                )

    conn.executemany(
        "INSERT OR REPLACE INTO countries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        country_rows,
    )
    conn.executemany(
        "INSERT OR REPLACE INTO states VALUES (?,?,?,?,?,?,?,?,?)",
        state_rows,
    )
    conn.executemany(
        "INSERT OR REPLACE INTO cities VALUES (?,?,?,?,?,?,?,?,?)",
        city_rows,
    )


def build_cache(
    *,
    url: str,
    destination: Path,
    timeout: float = 120.0,
    raw_bytes: bytes | None = None,
) -> Path:
    """Download (or accept) the dataset and write the SQLite cache atomically.

    `raw_bytes` exists so tests can supply a small fixture instead of hitting
    the network.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_payload(raw_bytes if raw_bytes is not None else _download(url, timeout))
    if not isinstance(payload, list):
        raise ValueError("Open dataset payload was not a list of countries.")

    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(destination.parent), prefix=".csc-", suffix=".tmp"
    )
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(SCHEMA)
            _insert_dataset(conn, payload)
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp_path, destination)
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info("Open geography cache built (%d countries)", len(payload))
    return destination
