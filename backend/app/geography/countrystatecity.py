"""CountryStateCity REST API provider.

Endpoint shapes (verified against docs.countrystatecity.in, 2026-10):
  GET /v1/countries
  GET /v1/countries/{ciso}/states
  GET /v1/countries/{ciso}/states/{siso}/cities
Authentication: `X-CSCAPI-KEY` header. The key is server-side only and is
never logged or returned.

The hosted free tier is metered (100 requests/day at time of writing), so every
call is charged against a `DailyQuota` before it is made. When the budget is
spent, `ProviderRateLimitedError` is raised and the service falls back to the
open dataset.
"""

from __future__ import annotations

import logging

import httpx

from app.errors import (
    InvalidCountryCodeError,
    InvalidStateCodeError,
    NotFoundError,
    ProviderAuthError,
    ProviderRateLimitedError,
    ProviderUpstreamError,
)
from app.geography.base import GeographyProvider
from app.geography.quota import DailyQuota
from app.geography.validation import normalize_country_code, normalize_state_code
from app.logging_config import redact_tokens
from app.schemas import City, Country, DataSource, ProviderName, StateRegion

logger = logging.getLogger(__name__)

ATTRIBUTION = "Data source: CountryStateCity API (countrystatecity.in)"
LICENSE = "CountryStateCity API terms"


def _as_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class CountryStateCityProvider(GeographyProvider):
    """Fetches geography data from the hosted CountryStateCity API."""

    name = ProviderName.COUNTRYSTATECITY.value

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        quota: DailyQuota,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._quota = quota
        self._client = client

    # -- lifecycle ---------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def is_available(self) -> bool:
        return self.configured and not self._quota.exhausted()

    def quota_remaining(self) -> int:
        return self._quota.remaining()

    # -- http --------------------------------------------------------------

    async def _get(self, path: str) -> object:
        if not self.configured:
            raise ProviderAuthError("CountryStateCity API key is not configured.")

        if not self._quota.try_consume():
            raise ProviderRateLimitedError(
                "CountryStateCity daily request budget exhausted; "
                "falling back to the open dataset."
            )

        headers = {"X-CSCAPI-KEY": self._api_key, "Accept": "application/json"}
        url = f"{self._base_url}{path}"
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderUpstreamError(
                "CountryStateCity request timed out."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUpstreamError(
                "CountryStateCity is unreachable."
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        return self._handle(response, path)

    def _handle(self, response: httpx.Response, path: str) -> object:
        status = response.status_code
        if status in (401, 403):
            raise ProviderAuthError(
                "CountryStateCity rejected the configured API key."
            )
        if status == 404:
            raise NotFoundError("CountryStateCity has no record for that path.")
        if status == 429:
            raise ProviderRateLimitedError(
                "CountryStateCity rate limit reached; falling back to the open dataset."
            )
        if status >= 500:
            raise ProviderUpstreamError(
                "CountryStateCity returned a server error."
            )
        if status != 200:
            raise ProviderUpstreamError(
                f"CountryStateCity returned an unexpected status ({status})."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            # Never echo the body: it may contain an echoed request URL.
            raise ProviderUpstreamError(
                "CountryStateCity returned a malformed JSON response."
            ) from exc
        if not isinstance(payload, list):
            logger.warning("Unexpected CountryStateCity payload for %s", redact_tokens(path))
            raise ProviderUpstreamError(
                "CountryStateCity returned an unexpected response shape."
            )
        return payload

    # -- mapping -----------------------------------------------------------

    @staticmethod
    def _to_country(raw: dict) -> Country:
        return Country(
            iso2=str(raw.get("iso2", "")).upper(),
            iso3=raw.get("iso3"),
            name=raw.get("name") or "",
            native_name=raw.get("native"),
            capital=raw.get("capital"),
            region=raw.get("region"),
            subregion=raw.get("subregion"),
            currency=raw.get("currency"),
            phonecode=raw.get("phonecode"),
            latitude=_as_float(raw.get("latitude")),
            longitude=_as_float(raw.get("longitude")),
            emoji=raw.get("emoji"),
        )

    @staticmethod
    def _to_state(raw: dict, country_iso2: str) -> StateRegion:
        return StateRegion(
            iso2=(raw.get("iso2") or None),
            name=raw.get("name") or "",
            native_name=raw.get("native"),
            type=raw.get("type"),
            country_iso2=country_iso2,
            latitude=_as_float(raw.get("latitude")),
            longitude=_as_float(raw.get("longitude")),
            timezone=raw.get("timezone"),
        )

    @staticmethod
    def _to_city(raw: dict, country_iso2: str, state_iso2: str) -> City:
        return City(
            name=raw.get("name") or "",
            native_name=raw.get("native"),
            country_iso2=country_iso2,
            state_iso2=state_iso2,
            latitude=_as_float(raw.get("latitude")),
            longitude=_as_float(raw.get("longitude")),
            timezone=raw.get("timezone"),
        )

    def _source(self) -> DataSource:
        return DataSource(
            provider=ProviderName.COUNTRYSTATECITY,
            attribution=ATTRIBUTION,
            license=LICENSE,
            cached=False,
            fallback_used=False,
        )

    # -- provider interface ------------------------------------------------

    async def list_countries(self) -> tuple[list[Country], DataSource]:
        payload = await self._get("/countries")
        countries = [self._to_country(r) for r in payload]  # type: ignore[union-attr]
        countries = [c for c in countries if c.iso2 and c.name]
        return countries, self._source()

    async def list_states(self, country_iso2: str) -> tuple[list[StateRegion], DataSource]:
        code = normalize_country_code(country_iso2)
        payload = await self._get(f"/countries/{code}/states")
        states = [self._to_state(r, code) for r in payload]  # type: ignore[union-attr]
        states = [s for s in states if s.name]
        if not states:
            raise NotFoundError(f"No states/regions found for country '{code}'.")
        return states, self._source()

    async def list_cities(
        self, country_iso2: str, state_iso2: str
    ) -> tuple[list[City], DataSource]:
        country = normalize_country_code(country_iso2)
        state = normalize_state_code(state_iso2)
        payload = await self._get(f"/countries/{country}/states/{state}/cities")
        cities = [self._to_city(r, country, state) for r in payload]  # type: ignore[union-attr]
        cities = [c for c in cities if c.name]
        if not cities:
            raise InvalidStateCodeError(
                f"No cities found for state '{state}' in country '{country}'."
            )
        return cities, self._source()
