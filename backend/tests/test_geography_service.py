"""Tests for provider selection, fallback, and provenance reporting.

The fallback path is the heart of Phase B's resilience story: when the hosted
provider is unconfigured, exhausted, or broken, the open dataset must serve the
request and the response must say so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import GeographyProviderChoice, Settings
from app.errors import NotFoundError, ProviderUnavailableError
from app.geography.base import GeographyProvider
from app.geography.open_dataset import OpenDatasetProvider
from app.geography.service import GeographyService, build_geography_service
from app.schemas import City, Country, DataSource, ProviderName, StateRegion


class StubProvider(GeographyProvider):
    """A provider whose behaviour is scripted per test.

    This is a deliberate, narrow test double: it stands in for *an upstream
    service we do not control* so the orchestration logic can be tested in
    isolation. Every other test in the suite exercises real implementations.
    """

    def __init__(self, name: str, *, available: bool = True, error: Exception | None = None):
        self.name = name
        self._available = available
        self._error = error

    @property
    def configured(self) -> bool:
        return True

    def is_available(self) -> bool:
        return self._available

    def _result(self):
        if self._error is not None:
            raise self._error
        return [], DataSource(
            provider=ProviderName.OPEN_DATASET,
            attribution=self.name,
        )

    async def list_countries(self):
        return self._result()

    async def list_states(self, country_iso2: str):
        return self._result()

    async def list_cities(self, country_iso2: str, state_iso2: str):
        return self._result()


def open_provider(cache: Path) -> OpenDatasetProvider:
    return OpenDatasetProvider(
        cache_path=cache,
        dataset_url="https://example.invalid/x.json.gz",
        attribution="Open dataset attribution",
        auto_build=False,
    )


async def test_uses_primary_when_available(built_cache: Path) -> None:
    primary = open_provider(built_cache)
    service = GeographyService(primary=primary, fallback=None)

    countries, source = await service.list_countries()
    assert len(countries) == 2
    assert source.provider is ProviderName.OPEN_DATASET
    assert source.fallback_used is False


async def test_falls_back_when_primary_fails(built_cache: Path) -> None:
    from app.errors import ProviderUpstreamError

    primary = StubProvider("countrystatecity", error=ProviderUpstreamError("boom"))
    fallback = open_provider(built_cache)
    service = GeographyService(primary=primary, fallback=fallback)

    countries, source = await service.list_countries()
    assert len(countries) == 2
    assert source.provider is ProviderName.OPEN_DATASET
    assert source.fallback_used is True
    assert "open dataset" in (source.notice or "")


async def test_falls_back_when_primary_unavailable(built_cache: Path) -> None:
    primary = StubProvider("countrystatecity", available=False)
    fallback = open_provider(built_cache)
    service = GeographyService(primary=primary, fallback=fallback)

    _, source = await service.list_countries()
    assert source.provider is ProviderName.OPEN_DATASET
    assert source.fallback_used is True


async def test_validation_error_is_not_masked_by_fallback(built_cache: Path) -> None:
    """A 400 from the primary is the caller's fault; do not silently retry."""
    from app.errors import InvalidCountryCodeError

    primary = StubProvider("countrystatecity", error=InvalidCountryCodeError("bad code"))
    fallback = open_provider(built_cache)
    service = GeographyService(primary=primary, fallback=fallback)

    with pytest.raises(InvalidCountryCodeError):
        await service.list_states("ZZ")


async def test_raises_when_no_provider_can_serve(tmp_path: Path) -> None:
    from app.errors import ProviderUpstreamError

    primary = StubProvider("countrystatecity", error=ProviderUpstreamError("down"))
    fallback = open_provider(tmp_path / "absent.sqlite3")
    service = GeographyService(primary=primary, fallback=fallback)

    with pytest.raises(ProviderUnavailableError):
        await service.list_countries()


async def test_not_found_propagates_as_404_not_503(built_cache: Path) -> None:
    """If every provider says 'no such record', the client must see 404."""
    primary = StubProvider("countrystatecity", error=NotFoundError("no such country"))
    fallback = open_provider(built_cache)
    service = GeographyService(primary=primary, fallback=fallback)

    with pytest.raises(NotFoundError):
        await service.list_states("ZZ")


async def test_primary_alone_falls_back_to_nothing(built_cache: Path) -> None:
    service = GeographyService(primary=open_provider(built_cache), fallback=None)
    _, source = await service.list_countries()
    assert source.fallback_used is False


def test_auto_selects_open_dataset_without_key(built_cache: Path) -> None:
    settings = Settings(
        geography_provider=GeographyProviderChoice.AUTO,
        csc_api_key="",
        open_dataset_cache_path=str(built_cache),
    )
    service = build_geography_service(settings)
    assert service.primary.name == "open_dataset"
    assert service.fallback is None


def test_auto_selects_csc_when_key_present(built_cache: Path) -> None:
    settings = Settings(
        geography_provider=GeographyProviderChoice.AUTO,
        csc_api_key="configured-key",
        open_dataset_cache_path=str(built_cache),
    )
    service = build_geography_service(settings)
    assert service.primary.name == "countrystatecity"
    assert service.fallback.name == "open_dataset"


def test_explicit_open_dataset_choice(built_cache: Path) -> None:
    settings = Settings(
        geography_provider=GeographyProviderChoice.OPEN_DATASET,
        csc_api_key="configured-key",  # ignored by this choice
        open_dataset_cache_path=str(built_cache),
    )
    service = build_geography_service(settings)
    assert service.primary.name == "open_dataset"
    assert service.fallback is None
