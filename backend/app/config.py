"""Application settings, loaded from environment / .env.

Secrets are read here and nowhere else. Nothing in this module is ever
serialised into an API response: `Settings.secret_values()` exists only so the
redaction helper can guarantee a token never leaks into a log line.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: backend/app/config.py -> backend/app -> backend -> <root>
REPO_ROOT = Path(__file__).resolve().parents[2]


class GeographyProviderChoice(str, Enum):
    """Which geography backend to prefer."""

    AUTO = "auto"
    COUNTRYSTATECITY = "countrystatecity"
    OPEN_DATASET = "open_dataset"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    geography_provider: GeographyProviderChoice = GeographyProviderChoice.AUTO

    # --- CountryStateCity (hosted, optional) ---
    csc_api_key: str = ""
    csc_daily_request_limit: int = Field(default=100, ge=0)
    csc_base_url: str = "https://api.countrystatecity.in/v1"
    csc_timeout_seconds: float = 15.0

    # --- Open dataset (free fallback) ---
    open_dataset_url: str = (
        "https://github.com/dr5hn/countries-states-cities-database/releases/"
        "download/v5.0.0-export.1/json-countries%2Bstates%2Bcities.json.gz"
    )
    open_dataset_attribution: str = (
        "Data source: countries-states-cities-database (ODbL-1.0), "
        "https://github.com/dr5hn/countries-states-cities-database"
    )
    open_dataset_cache_path: str = "backend/data/csc.sqlite3"
    open_dataset_auto_build: bool = True
    open_dataset_download_timeout: float = 120.0

    # --- Google Maps (intentionally unconfigured by default) ---
    google_maps_api_key: str = ""

    @field_validator("csc_api_key", "google_maps_api_key", mode="before")
    @classmethod
    def _blank_secrets(cls, value: object) -> object:
        """Treat a whitespace-only secret as absent."""
        if isinstance(value, str) and not value.strip():
            return ""
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def cache_file(self) -> Path:
        """Absolute path to the generated SQLite cache."""
        path = Path(self.open_dataset_cache_path)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def csc_configured(self) -> bool:
        return bool(self.csc_api_key)

    @property
    def google_maps_configured(self) -> bool:
        return bool(self.google_maps_api_key)

    def secret_values(self) -> list[str]:
        """Secret strings that must never appear in logs or responses."""
        return [v for v in (self.csc_api_key, self.google_maps_api_key) if v]


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    """Drop the cached settings. Used by tests."""
    global _settings
    _settings = None
