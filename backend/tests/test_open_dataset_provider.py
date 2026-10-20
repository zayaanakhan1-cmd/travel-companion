"""Tests for the open-dataset provider.

These exercise the real SQLite cache built by the production builder from a
fixture shaped like the upstream dataset. No mocks: real SQL, real database,
real provider code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import NotFoundError, ProviderUnavailableError
from app.geography.dataset_builder import build_cache
from app.geography.open_dataset import OpenDatasetProvider
from app.schemas import ProviderName

ATTRIBUTION = "Test attribution (ODbL-1.0)"


def make_provider(cache: Path, *, auto_build: bool = False) -> OpenDatasetProvider:
    return OpenDatasetProvider(
        cache_path=cache,
        dataset_url="https://example.invalid/dataset.json.gz",
        attribution=ATTRIBUTION,
        auto_build=auto_build,
    )


async def test_builds_cache_from_fixture(built_cache: Path) -> None:
    assert built_cache.exists()
    assert built_cache.stat().st_size > 0


async def test_lists_countries_sorted(built_cache: Path) -> None:
    provider = make_provider(built_cache)
    countries, source = await provider.list_countries()

    assert [c.iso2 for c in countries] == ["CA", "IN"]
    assert countries[1].name == "India"
    assert countries[1].capital == "New Delhi"
    assert countries[1].native_name == "भारत"
    assert countries[1].latitude == pytest.approx(20.0)
    assert countries[1].emoji == "🇮🇳"

    assert source.provider is ProviderName.OPEN_DATASET
    assert source.attribution == ATTRIBUTION
    assert source.license == "ODbL-1.0"
    assert source.cached is True
    assert source.fallback_used is False


async def test_lists_states_for_country(built_cache: Path) -> None:
    provider = make_provider(built_cache)
    states, source = await provider.list_states("in")  # lower-case on purpose

    assert [s.name for s in states] == ["Goa", "Maharashtra"]
    assert all(s.country_iso2 == "IN" for s in states)
    assert states[1].iso2 == "MH"
    assert states[1].type == "state"
    assert states[1].timezone == "Asia/Kolkata"
    assert source.provider is ProviderName.OPEN_DATASET


async def test_lists_cities_for_state(built_cache: Path) -> None:
    provider = make_provider(built_cache)
    cities, _ = await provider.list_cities("IN", "MH")

    assert [c.name for c in cities] == ["Mumbai", "Pune"]
    assert all(c.country_iso2 == "IN" for c in cities)
    assert all(c.state_iso2 == "MH" for c in cities)
    assert cities[0].latitude == pytest.approx(19.07283)


async def test_unknown_country_raises_not_found(built_cache: Path) -> None:
    provider = make_provider(built_cache)
    with pytest.raises(NotFoundError, match="Unknown country code 'ZZ'"):
        await provider.list_states("ZZ")


async def test_state_with_no_cities_raises_clear_error(built_cache: Path) -> None:
    """Goa exists but has no cities: the message must say so, not 'not found'."""
    provider = make_provider(built_cache)
    with pytest.raises(NotFoundError, match="no cities for 'IN-GA'"):
        await provider.list_cities("IN", "GA")


async def test_unknown_state_raises_not_found(built_cache: Path) -> None:
    provider = make_provider(built_cache)
    with pytest.raises(NotFoundError, match="No state/region 'ZZ' in country 'IN'"):
        await provider.list_cities("IN", "ZZ")


async def test_sql_injection_attempt_is_rejected_before_sql(built_cache: Path) -> None:
    """A hostile code never reaches the query: validation rejects it first."""
    from app.errors import InvalidStateCodeError

    provider = make_provider(built_cache)
    with pytest.raises(InvalidStateCodeError):
        await provider.list_cities("IN", "MH' OR '1'='1")


async def test_missing_cache_without_auto_build_is_unavailable(tmp_path: Path) -> None:
    provider = make_provider(tmp_path / "absent.sqlite3", auto_build=False)
    assert provider.configured is False
    with pytest.raises(ProviderUnavailableError, match="cache is missing"):
        await provider.list_countries()


async def test_cache_is_built_on_demand(
    cache_path: Path, dataset_payload_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """auto_build=True should construct the cache on first use.

    Only the network read is replaced: the real builder, real gzip decoding,
    and real SQLite writes all execute.
    """
    import app.geography.open_dataset as module
    from app.geography import dataset_builder

    def builder_using_fixture(*, url: str, destination: Path, timeout: float) -> Path:
        return dataset_builder.build_cache(
            url=url,
            destination=destination,
            timeout=timeout,
            raw_bytes=dataset_payload_bytes,
        )

    monkeypatch.setattr(module, "build_cache", builder_using_fixture)

    provider = make_provider(cache_path, auto_build=True)
    assert not cache_path.exists()
    countries, _ = await provider.list_countries()
    assert cache_path.exists()
    assert len(countries) == 2


async def test_connection_is_reused_and_closed(built_cache: Path) -> None:
    provider = make_provider(built_cache)
    await provider.list_countries()
    assert provider._conn is not None
    await provider.aclose()
    assert provider._conn is None
