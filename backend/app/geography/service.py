"""Geography service: provider selection, fallback, and provenance.

Order of preference:
  * `countrystatecity` - hosted API, only when a key is configured and the
    daily budget is unspent.
  * `open_dataset` - always-available local cache. Genuinely free.

`auto` picks CountryStateCity when configured, else the open dataset. Whenever
a preferred provider fails or is exhausted, the service falls back and marks
`source.fallback_used = True` so the UI can be honest about provenance.
"""

from __future__ import annotations

import logging

from app.config import GeographyProviderChoice, Settings
from app.errors import GeographyError, NotFoundError, ProviderUnavailableError
from app.geography.base import GeographyProvider
from app.geography.quota import DailyQuota
from app.schemas import City, Country, DataSource, StateRegion

logger = logging.getLogger(__name__)


class GeographyService:
    """Coordinates providers and normalises fallback behaviour."""

    def __init__(
        self,
        *,
        primary: GeographyProvider | None,
        fallback: GeographyProvider | None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def primary(self) -> GeographyProvider | None:
        return self._primary

    @property
    def fallback(self) -> GeographyProvider | None:
        return self._fallback

    async def _run(self, method: str, *args) -> tuple[list, DataSource]:
        errors: list[str] = []
        # A 404 is a definitive answer about the request, not a provider
        # outage. Remember it so that if every provider declines, the client
        # still gets 404 rather than a misleading 503.
        not_found: NotFoundError | None = None

        if self._primary is not None and self._primary.is_available():
            try:
                data, source = await getattr(self._primary, method)(*args)
                return data, source
            except NotFoundError as exc:
                not_found = not_found or exc
                errors.append(f"{self._primary.name}: {exc.code}")
            except GeographyError as exc:
                # A validation error is the caller's fault, not the provider's:
                # do not mask it by silently retrying another source.
                if exc.http_status == 400:
                    raise
                errors.append(f"{self._primary.name}: {exc.code}")
                logger.warning(
                    "Primary geography provider failed (%s); trying fallback",
                    exc.code,
                )

        if self._fallback is not None and self._fallback.is_available():
            try:
                data, source = await getattr(self._fallback, method)(*args)
                source.fallback_used = bool(errors) or (
                    self._primary is not None and self._primary.name != source.provider
                )
                if errors:
                    source.notice = (
                        "Primary provider unavailable; served from the open dataset."
                    )
                return data, source
            except NotFoundError as exc:
                not_found = not_found or exc
                errors.append(f"{self._fallback.name}: {exc.code}")
            except GeographyError as exc:
                if exc.http_status == 400:
                    raise
                errors.append(f"{self._fallback.name}: {exc.code}")

        if not_found is not None:
            raise not_found

        raise ProviderUnavailableError(
            "No geography provider could serve this request"
            + (f" ({'; '.join(errors)})" if errors else ".")
        )

    async def list_countries(self) -> tuple[list[Country], DataSource]:
        return await self._run("list_countries")

    async def list_states(self, country_iso2: str) -> tuple[list[StateRegion], DataSource]:
        return await self._run("list_states", country_iso2)

    async def list_cities(
        self, country_iso2: str, state_iso2: str
    ) -> tuple[list[City], DataSource]:
        return await self._run("list_cities", country_iso2, state_iso2)


def build_geography_service(settings: Settings) -> GeographyService:
    """Wire providers according to configuration."""
    # Imported here so tests can patch settings without import-time side effects.
    from app.geography.countrystatecity import CountryStateCityProvider
    from app.geography.open_dataset import OpenDatasetProvider

    open_provider = OpenDatasetProvider(
        cache_path=settings.cache_file,
        dataset_url=settings.open_dataset_url,
        attribution=settings.open_dataset_attribution,
        auto_build=settings.open_dataset_auto_build,
        download_timeout=settings.open_dataset_download_timeout,
    )

    csc_provider: CountryStateCityProvider | None = None
    if settings.csc_configured:
        csc_provider = CountryStateCityProvider(
            api_key=settings.csc_api_key,
            base_url=settings.csc_base_url,
            timeout=settings.csc_timeout_seconds,
            quota=DailyQuota(settings.csc_daily_request_limit),
        )

    choice = settings.geography_provider
    if choice is GeographyProviderChoice.OPEN_DATASET:
        return GeographyService(primary=open_provider, fallback=None)
    if choice is GeographyProviderChoice.COUNTRYSTATECITY:
        return GeographyService(primary=csc_provider, fallback=open_provider)
    # AUTO
    if csc_provider is not None:
        return GeographyService(primary=csc_provider, fallback=open_provider)
    return GeographyService(primary=open_provider, fallback=None)
