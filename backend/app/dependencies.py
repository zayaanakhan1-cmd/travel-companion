"""FastAPI dependency wiring."""

from __future__ import annotations

from fastapi import Request

from app.config import Settings, get_settings
from app.geography.google_maps import GoogleMapsAdapter
from app.geography.service import GeographyService, build_geography_service


def get_geography_service(request: Request) -> GeographyService:
    """Return the geography service created during app startup."""
    return request.app.state.geography_service


def get_app_settings(request: Request) -> Settings:
    """Return the settings instance created during app startup."""
    return request.app.state.settings


def get_google_maps_adapter(request: Request) -> GoogleMapsAdapter:
    """Return the (unconfigured) Google Maps adapter."""
    return request.app.state.google_maps_adapter


def create_geography_service(settings: Settings) -> GeographyService:
    return build_geography_service(settings)


__all__ = [
    "create_geography_service",
    "get_app_settings",
    "get_geography_service",
    "get_google_maps_adapter",
    "get_settings",
]
