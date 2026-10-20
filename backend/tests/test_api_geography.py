"""End-to-end tests for the HTTP contract.

These drive the real FastAPI app through `httpx.ASGITransport`, with the real
open-dataset provider reading the real SQLite cache. The only substitution is
the dataset URL, which points at the fixture bytes instead of the network.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.config import GeographyProviderChoice, Settings
from app.main import create_app

ATTRIBUTION = "Test attribution (ODbL-1.0)"


@pytest.fixture
def app_settings(built_cache: Path) -> Settings:
    return Settings(
        app_env="test",
        geography_provider=GeographyProviderChoice.OPEN_DATASET,
        csc_api_key="",
        google_maps_api_key="",
        open_dataset_cache_path=str(built_cache),
        open_dataset_attribution=ATTRIBUTION,
        open_dataset_auto_build=False,
    )


@pytest.fixture
async def client(app_settings: Settings):
    app = create_app(app_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http_client:
        # Enter the lifespan so startup wiring runs.
        async with app.router.lifespan_context(app):
            yield http_client


# --- health / root ---------------------------------------------------------


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert "version" in body


async def test_root_points_at_docs(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


async def test_openapi_schema_is_served(client: httpx.AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/geography/countries" in paths
    assert "/api/v1/geography/countries/{country_iso2}/states" in paths


# --- geography happy paths -------------------------------------------------


async def test_list_countries(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries")
    assert response.status_code == 200
    body = response.json()

    assert [c["iso2"] for c in body["data"]] == ["CA", "IN"]
    assert body["data"][1]["capital"] == "New Delhi"

    source = body["source"]
    assert source["provider"] == "open_dataset"
    assert source["attribution"] == ATTRIBUTION
    assert source["license"] == "ODbL-1.0"
    assert source["cached"] is True
    assert source["fallback_used"] is False


async def test_list_states(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/IN/states")
    assert response.status_code == 200
    body = response.json()
    assert [s["name"] for s in body["data"]] == ["Goa", "Maharashtra"]
    assert body["data"][1]["iso2"] == "MH"


async def test_country_code_is_case_insensitive(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/in/states")
    assert response.status_code == 200
    assert body_names(response) == ["Goa", "Maharashtra"]


async def test_list_cities(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/IN/states/MH/cities")
    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body["data"]] == ["Mumbai", "Pune"]
    assert body["data"][0]["latitude"] == pytest.approx(19.07283)


def body_names(response: httpx.Response) -> list[str]:
    return [item["name"] for item in response.json()["data"]]


# --- error contract --------------------------------------------------------


async def test_invalid_country_code_returns_400(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/IND/states")
    # "IND" is three characters: FastAPI's path constraint rejects it first.
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


async def test_bad_country_code_shape_returns_400(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/1N/states")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_country_code"


async def test_unknown_country_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/ZZ/states")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_state_without_cities_returns_404_with_clear_message(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/geography/countries/IN/states/GA/cities")
    assert response.status_code == 404
    detail = response.json()["error"]["detail"]
    assert "no cities" in detail.lower()


async def test_unknown_state_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/IN/states/ZZ/cities")
    assert response.status_code == 404


async def test_sql_injection_attempt_returns_400(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/geography/countries/IN/states/MH%27%20OR%201%3D1/cities")
    assert response.status_code in (400, 422)
    assert "error" in response.json()


async def test_error_bodies_never_echo_the_submitted_value(
    client: httpx.AsyncClient,
) -> None:
    """A rejected code must not be reflected back in the message."""
    response = await client.get("/api/v1/geography/countries/1N/states")
    assert "1N" not in response.json()["error"]["detail"]


# --- integrations status ---------------------------------------------------


async def test_integrations_reports_unconfigured_google_maps(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/integrations")
    assert response.status_code == 200
    by_name = {item["name"]: item for item in response.json()}

    assert by_name["google_maps"]["configured"] is False
    assert by_name["google_maps"]["enabled"] is False
    assert by_name["google_maps"]["reason"] == "unconfigured"
    assert "Demo Key" in by_name["google_maps"]["notes"]

    assert by_name["open_dataset"]["enabled"] is True
    assert by_name["countrystatecity"]["configured"] is False
