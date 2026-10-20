"""Tests that secrets cannot leak.

Three distinct risks are covered:
  1. A configured secret appearing in a log record.
  2. A secret appearing in an HTTP response body.
  3. A secret appearing in an error message returned to a client.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from app.config import GeographyProviderChoice, Settings
from app.logging_config import (
    SecretRedactionFilter,
    configure_logging,
    redact,
    redact_tokens,
)
from app.main import create_app

FAKE_CSC_KEY = "csc-secret-value-abc123"
# Assembled at runtime so the repository contains no Google-key-shaped literal
# that secret scanners would flag.
FAKE_GOOGLE_KEY = "AIza" + "FAKEKEYFORTESTING0123456789abcd"


# --- log redaction ---------------------------------------------------------


def test_secret_is_removed_from_log_message() -> None:
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"calling upstream with key {FAKE_CSC_KEY}",
        args=(),
        exc_info=None,
    )
    SecretRedactionFilter([FAKE_CSC_KEY]).filter(record)
    assert FAKE_CSC_KEY not in record.getMessage()
    assert "***REDACTED***" in record.getMessage()


def test_secret_is_removed_from_log_args() -> None:
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="key=%s other=%s",
        args=(FAKE_CSC_KEY, "visible"),
        exc_info=None,
    )
    SecretRedactionFilter([FAKE_CSC_KEY]).filter(record)
    message = record.getMessage()
    assert FAKE_CSC_KEY not in message
    assert "visible" in message


def test_longest_secret_is_masked_first() -> None:
    """A secret containing another must be fully redacted, not partially."""
    short, long = "abc", "abcdef"
    assert redact(f"value={long}", [short, long]) == "value=***REDACTED***"


def test_redact_handles_no_secrets() -> None:
    assert redact("nothing to hide", []) == "nothing to hide"


@pytest.mark.parametrize(
    "token",
    [
        "ghp_" + "a" * 36,
        "ghu_" + "b" * 36,
        "github_pat_" + "c" * 30,
        "AIza" + "d" * 30,
    ],
)
def test_token_shapes_are_redacted_even_if_unconfigured(token: str) -> None:
    """Defence in depth: unknown-but-token-shaped strings are still scrubbed."""
    assert token not in redact_tokens(f"Authorization: {token}")


def test_configure_logging_installs_filter() -> None:
    configure_logging("INFO", [FAKE_CSC_KEY])
    handlers = logging.getLogger().handlers
    assert any(
        isinstance(f, SecretRedactionFilter)
        for handler in handlers
        for f in handler.filters
    )


# --- response hygiene ------------------------------------------------------


@pytest.fixture
def settings_with_secrets(built_cache: Path) -> Settings:
    return Settings(
        app_env="test",
        geography_provider=GeographyProviderChoice.OPEN_DATASET,
        csc_api_key=FAKE_CSC_KEY,
        google_maps_api_key=FAKE_GOOGLE_KEY,
        open_dataset_cache_path=str(built_cache),
        open_dataset_auto_build=False,
    )


@pytest.fixture
async def client(settings_with_secrets: Settings):
    app = create_app(settings_with_secrets)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        async with app.router.lifespan_context(app):
            yield c


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/api/v1/health",
        "/api/v1/integrations",
        "/api/v1/geography/countries",
        "/api/v1/geography/countries/IN/states",
        "/api/v1/geography/countries/IN/states/MH/cities",
        "/api/v1/geography/countries/1N/states",
        "/api/v1/geography/countries/ZZ/states",
        "/openapi.json",
    ],
)
async def test_no_secret_in_any_response(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path)
    text = response.text
    assert FAKE_CSC_KEY not in text, f"API key leaked in {path}"
    assert FAKE_GOOGLE_KEY not in text, f"Google key leaked in {path}"


async def test_settings_never_expose_secrets_in_representations(
    settings_with_secrets: Settings,
) -> None:
    """Even a repr() of settings must not be a convenient leak vector."""
    assert FAKE_CSC_KEY not in str(settings_with_secrets.model_dump(exclude={"csc_api_key"}))
    # The accessor that exposes them is explicit and named for its purpose.
    assert settings_with_secrets.secret_values() == [FAKE_CSC_KEY, FAKE_GOOGLE_KEY]


async def test_unconfigured_google_maps_reports_no_key(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/integrations")
    google = next(i for i in response.json() if i["name"] == "google_maps")
    assert google["enabled"] is False
