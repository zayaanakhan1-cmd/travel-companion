"""Pydantic models shared across the API.

These are the contract. Every geography provider must return data that
validates against these models, so the frontend can rely on one stable shape
regardless of which upstream source served the request.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProviderName(str, Enum):
    """Identifies which data source produced a response."""

    COUNTRYSTATECITY = "countrystatecity"
    OPEN_DATASET = "open_dataset"
    UNAVAILABLE = "unavailable"


class DataSource(BaseModel):
    """Provenance for a response, so the UI can attribute the data."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    attribution: str = Field(..., description="Human-readable attribution text.")
    license: str | None = Field(
        default=None, description="SPDX-ish licence identifier, when known."
    )
    cached: bool = Field(
        default=False, description="True when served from a local cache."
    )
    fallback_used: bool = Field(
        default=False,
        description="True when the preferred provider failed or was exhausted.",
    )
    notice: str | None = Field(
        default=None,
        description="Set when data is degraded, mocked, or partly unavailable.",
    )


class Country(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iso2: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2.")
    iso3: str | None = Field(default=None, description="ISO 3166-1 alpha-3.")
    name: str
    native_name: str | None = None
    capital: str | None = None
    region: str | None = None
    subregion: str | None = None
    currency: str | None = None
    phonecode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    emoji: str | None = None


class StateRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iso2: str | None = Field(
        default=None,
        description=(
            "Subdivision code. For CountryStateCity this is the state code used "
            "in downstream city lookups; for the open dataset it is ISO 3166-2 "
            "without the country prefix. May be null for some subdivisions."
        ),
    )
    name: str
    native_name: str | None = None
    type: str | None = Field(default=None, description="e.g. province, district.")
    country_iso2: str = Field(..., min_length=2, max_length=2)
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None


class City(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    native_name: str | None = None
    country_iso2: str = Field(..., min_length=2, max_length=2)
    state_iso2: str | None = None
    state_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None


class CountryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[Country]
    source: DataSource


class StateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[StateRegion]
    source: DataSource


class CityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[City]
    source: DataSource


class ProviderStatus(BaseModel):
    """Reports whether an integration is live, degraded, or unconfigured."""

    model_config = ConfigDict(extra="forbid")

    name: str
    configured: bool
    enabled: bool
    reason: str
    notes: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    version: str
    environment: str
