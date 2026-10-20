"""Tests for the CountryStateCity provider.

Rather than mocking httpx, these tests run a real local HTTP server that
speaks the same contract as the upstream API (paths, `X-CSCAPI-KEY` header,
JSON list bodies, 401/404/429/500 status codes). The provider's real client
code path executes end to end.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.errors import (
    InvalidStateCodeError,
    NotFoundError,
    ProviderAuthError,
    ProviderRateLimitedError,
    ProviderUpstreamError,
)
from app.geography.countrystatecity import CountryStateCityProvider
from app.geography.quota import DailyQuota

API_KEY = "test-key-not-a-real-secret"

COUNTRIES = [
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
    }
]
STATES = [
    {
        "id": 4008,
        "name": "Maharashtra",
        "iso2": "MH",
        "country_id": 101,
        "country_code": "IN",
        "latitude": "19.75147980",
        "longitude": "75.71388840",
        "timezone": "Asia/Kolkata",
    }
]
CITIES = [
    {
        "id": 133024,
        "name": "Mumbai",
        "latitude": "19.07283000",
        "longitude": "72.88261000",
        "timezone": "Asia/Kolkata",
    }
]


class _Handler(BaseHTTPRequestHandler):
    """Fake CountryStateCity API. Behaviour is driven by `server.scenario`."""

    def log_message(self, *args) -> None:  # silence test output
        pass

    def _send(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        scenario = self.server.scenario  # type: ignore[attr-defined]
        self.server.seen_paths.append(self.path)  # type: ignore[attr-defined]
        self.server.seen_keys.append(self.headers.get("X-CSCAPI-KEY"))  # type: ignore[attr-defined]

        if scenario == "unauthorized":
            self._send(401, {"message": "Unauthorized"})
            return
        if scenario == "rate_limited":
            self._send(429, {"message": "Too many requests"})
            return
        if scenario == "server_error":
            self._send(500, {"message": "boom"})
            return
        if scenario == "malformed":
            raw = b"<html>not json</html>"
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if scenario == "unexpected_shape":
            self._send(200, {"not": "a list"})
            return

        path = self.path
        # Validate the path shape strictly, so an unexpected path is a real 404
        # rather than accidentally matching a prefix.
        resource = path.split("/v1", 1)[-1]
        if resource == "/countries":
            self._send(200, COUNTRIES)
        elif re.fullmatch(r"/countries/[A-Z]{2}/states", resource):
            self._send(200, STATES)
        elif re.fullmatch(r"/countries/[A-Z]{2}/states/[A-Z0-9]{1,6}/cities", resource):
            self._send(200, CITIES)
        else:
            self._send(404, {"message": "Not Found"})


@pytest.fixture
def api_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.scenario = "ok"  # type: ignore[attr-defined]
    server.seen_paths = []  # type: ignore[attr-defined]
    server.seen_keys = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def api_server_empty_cities():
    server = HTTPServer(("127.0.0.1", 0), _EmptyCitiesHandler)
    server.scenario = "ok"  # type: ignore[attr-defined]
    server.seen_paths = []  # type: ignore[attr-defined]
    server.seen_keys = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def make_provider(server, *, limit: int = 100, api_key: str = API_KEY):
    host, port = server.server_address
    return CountryStateCityProvider(
        api_key=api_key,
        base_url=f"http://{host}:{port}/v1",
        timeout=5.0,
        quota=DailyQuota(limit),
    )


async def test_lists_countries(api_server) -> None:
    provider = make_provider(api_server)
    countries, source = await provider.list_countries()

    assert len(countries) == 1
    assert countries[0].iso2 == "IN"
    assert countries[0].name == "India"
    assert countries[0].latitude == pytest.approx(20.0)
    assert source.provider.value == "countrystatecity"
    assert api_server.seen_paths == ["/v1/countries"]


async def test_lists_states_and_normalises_country_code(api_server) -> None:
    provider = make_provider(api_server)
    states, _ = await provider.list_states("in")

    assert [s.name for s in states] == ["Maharashtra"]
    assert states[0].country_iso2 == "IN"
    assert api_server.seen_paths == ["/v1/countries/IN/states"]


async def test_lists_cities(api_server) -> None:
    provider = make_provider(api_server)
    cities, _ = await provider.list_cities("in", "mh")

    assert [c.name for c in cities] == ["Mumbai"]
    assert cities[0].state_iso2 == "MH"
    assert api_server.seen_paths == ["/v1/countries/IN/states/MH/cities"]


async def test_api_key_is_sent_as_header(api_server) -> None:
    provider = make_provider(api_server)
    await provider.list_countries()
    assert api_server.seen_keys == [API_KEY]


async def test_401_raises_auth_error(api_server) -> None:
    api_server.scenario = "unauthorized"
    provider = make_provider(api_server)
    with pytest.raises(ProviderAuthError):
        await provider.list_countries()


async def test_429_raises_rate_limited(api_server) -> None:
    api_server.scenario = "rate_limited"
    provider = make_provider(api_server)
    with pytest.raises(ProviderRateLimitedError):
        await provider.list_countries()


async def test_500_raises_upstream_error(api_server) -> None:
    api_server.scenario = "server_error"
    provider = make_provider(api_server)
    with pytest.raises(ProviderUpstreamError):
        await provider.list_countries()


async def test_malformed_json_raises_upstream_error(api_server) -> None:
    api_server.scenario = "malformed"
    provider = make_provider(api_server)
    with pytest.raises(ProviderUpstreamError, match="malformed JSON"):
        await provider.list_countries()


async def test_unexpected_shape_raises_upstream_error(api_server) -> None:
    api_server.scenario = "unexpected_shape"
    provider = make_provider(api_server)
    with pytest.raises(ProviderUpstreamError, match="unexpected response shape"):
        await provider.list_countries()


async def test_unknown_path_raises_not_found(api_server) -> None:
    provider = make_provider(api_server)
    provider._base_url = provider._base_url + "/nonexistent"
    with pytest.raises(NotFoundError):
        await provider.list_countries()


async def test_quota_is_charged_per_request(api_server) -> None:
    provider = make_provider(api_server, limit=2)
    await provider.list_countries()
    assert provider.quota_remaining() == 1
    await provider.list_states("IN")
    assert provider.quota_remaining() == 0
    assert provider.is_available() is False
    with pytest.raises(ProviderRateLimitedError):
        await provider.list_countries()


async def test_quota_is_not_charged_for_rejected_input(api_server) -> None:
    """Validation happens before the request, so it must not spend budget."""
    provider = make_provider(api_server, limit=5)
    with pytest.raises(Exception):
        await provider.list_cities("IN", "MH' OR 1=1")
    assert provider.quota_remaining() == 5


class _EmptyCitiesHandler(_Handler):
    """Same API, but the cities endpoint returns an empty list."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path.endswith("/cities"):
            self.server.seen_paths.append(self.path)  # type: ignore[attr-defined]
            self._send(200, [])
            return
        super().do_GET()


async def test_empty_city_list_for_known_state_raises(api_server_empty_cities) -> None:
    provider = make_provider(api_server_empty_cities)
    with pytest.raises(InvalidStateCodeError, match="No cities found"):
        await provider.list_cities("IN", "MH")


async def test_unconfigured_provider_is_unavailable() -> None:
    provider = CountryStateCityProvider(
        api_key="",
        base_url="http://127.0.0.1:1/v1",
        timeout=1.0,
        quota=DailyQuota(10),
    )
    assert provider.configured is False
    assert provider.is_available() is False
    with pytest.raises(ProviderAuthError):
        await provider.list_countries()
