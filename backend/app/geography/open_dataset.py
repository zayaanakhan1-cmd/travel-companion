"""Open-dataset geography provider.

Reads the SQLite cache produced by `dataset_builder`. This is the genuinely
free path: no API key, no quota, and no network at query time. It is the
default when no CountryStateCity key is configured, and the fallback whenever
that provider is exhausted or failing.

Licence note: the upstream database is ODbL-1.0, which requires attribution.
`DataSource.attribution` carries the required notice to every client.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path

from app.errors import (
    NotFoundError,
    ProviderUnavailableError,
)
from app.geography.base import GeographyProvider
from app.geography.dataset_builder import build_cache
from app.geography.validation import normalize_country_code, normalize_state_code
from app.schemas import City, Country, DataSource, ProviderName, StateRegion

logger = logging.getLogger(__name__)


def _as_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class OpenDatasetProvider(GeographyProvider):
    """Serves geography data from a locally cached ODbL dataset."""

    name = ProviderName.OPEN_DATASET.value

    def __init__(
        self,
        *,
        cache_path: Path,
        dataset_url: str,
        attribution: str,
        auto_build: bool = True,
        download_timeout: float = 120.0,
    ) -> None:
        self._cache_path = cache_path
        self._dataset_url = dataset_url
        self._attribution = attribution
        self._auto_build = auto_build
        self._download_timeout = download_timeout
        # One lock guards both cache construction and connection use, so the
        # first concurrent requests cannot race to build the same file.
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = None

    # -- lifecycle ---------------------------------------------------------

    @property
    def configured(self) -> bool:
        """True when the cache exists, or can be built on demand."""
        return self._cache_path.exists() or self._auto_build

    def is_available(self) -> bool:
        return self.configured

    @property
    def cache_exists(self) -> bool:
        return self._cache_path.exists()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._cache_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    async def _ensure_cache(self) -> None:
        if self._cache_path.exists():
            return
        if not self._auto_build:
            raise ProviderUnavailableError(
                "The open geography dataset cache is missing and auto-build is "
                "disabled. Run `python -m app.geography` or set "
                "OPEN_DATASET_AUTO_BUILD=true."
            )
        async with self._lock:
            if self._cache_path.exists():
                return
            try:
                await asyncio.to_thread(
                    build_cache,
                    url=self._dataset_url,
                    destination=self._cache_path,
                    timeout=self._download_timeout,
                )
            except Exception as exc:  # network / parse failures
                raise ProviderUnavailableError(
                    "Could not build the open geography dataset cache. "
                    "Check network access or pre-build it."
                ) from exc

    async def _get_conn(self) -> sqlite3.Connection:
        await self._ensure_cache()
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    async def aclose(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _source(self, *, notice: str | None = None) -> DataSource:
        return DataSource(
            provider=ProviderName.OPEN_DATASET,
            attribution=self._attribution,
            license="ODbL-1.0",
            cached=True,
            fallback_used=False,
            notice=notice,
        )

    async def _query(self, sql: str, params: tuple) -> list[sqlite3.Row]:
        conn = await self._get_conn()
        async with self._lock:
            cursor = conn.execute(sql, params)
            try:
                return cursor.fetchall()
            finally:
                cursor.close()

    # -- mapping -----------------------------------------------------------

    @staticmethod
    def _to_country(row: sqlite3.Row) -> Country:
        return Country(
            iso2=row["iso2"],
            iso3=row["iso3"],
            name=row["name"],
            native_name=row["native"],
            capital=row["capital"],
            region=row["region"],
            subregion=row["subregion"],
            currency=row["currency"],
            phonecode=row["phonecode"],
            latitude=_as_float(row["latitude"]),
            longitude=_as_float(row["longitude"]),
            emoji=row["emoji"],
        )

    @staticmethod
    def _to_state(row: sqlite3.Row) -> StateRegion:
        return StateRegion(
            iso2=row["iso2"] or None,
            name=row["name"],
            type=row["type"],
            country_iso2=row["country_code"],
            latitude=_as_float(row["latitude"]),
            longitude=_as_float(row["longitude"]),
            timezone=row["timezone"],
        )

    @staticmethod
    def _to_city(row: sqlite3.Row) -> City:
        return City(
            name=row["name"],
            country_iso2=row["country_code"],
            state_iso2=row["state_code"] or None,
            latitude=_as_float(row["latitude"]),
            longitude=_as_float(row["longitude"]),
            timezone=row["timezone"],
        )

    # -- provider interface ------------------------------------------------

    async def list_countries(self) -> tuple[list[Country], DataSource]:
        rows = await self._query(
            "SELECT * FROM countries ORDER BY name COLLATE NOCASE", ()
        )
        countries = [self._to_country(r) for r in rows if r["iso2"]]
        if not countries:
            raise NotFoundError("The open dataset contains no countries.")
        return countries, self._source()

    async def list_states(self, country_iso2: str) -> tuple[list[StateRegion], DataSource]:
        code = normalize_country_code(country_iso2)
        rows = await self._query(
            "SELECT * FROM states WHERE country_code = ? ORDER BY name COLLATE NOCASE",
            (code,),
        )
        if not rows:
            # Distinguish "unknown country" from "country with no subdivisions".
            exists = await self._query(
                "SELECT 1 FROM countries WHERE iso2 = ? LIMIT 1", (code,)
            )
            if not exists:
                raise NotFoundError(f"Unknown country code '{code}'.")
            raise NotFoundError(
                f"The open dataset has no states/regions for '{code}'."
            )
        return [self._to_state(r) for r in rows], self._source()

    async def list_cities(
        self, country_iso2: str, state_iso2: str
    ) -> tuple[list[City], DataSource]:
        country = normalize_country_code(country_iso2)
        state = normalize_state_code(state_iso2)
        rows = await self._query(
            """
            SELECT * FROM cities
            WHERE country_code = ? AND state_code = ?
            ORDER BY name COLLATE NOCASE
            """,
            (country, state),
        )
        if not rows:
            state_exists = await self._query(
                "SELECT 1 FROM states WHERE country_code = ? AND iso2 = ? LIMIT 1",
                (country, state),
            )
            if not state_exists:
                raise NotFoundError(
                    f"No state/region '{state}' in country '{country}'."
                )
            raise NotFoundError(
                f"The open dataset has no cities for '{country}-{state}'."
            )
        return [self._to_city(r) for r in rows], self._source()
