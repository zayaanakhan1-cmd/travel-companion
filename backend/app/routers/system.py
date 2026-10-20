"""Health and integration-status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.config import Settings
from app.dependencies import (
    get_app_settings,
    get_geography_service,
    get_google_maps_adapter,
)
from app.geography.base import GeographyProvider
from app.geography.google_maps import GoogleMapsAdapter
from app.geography.service import GeographyService
from app.schemas import HealthResponse, ProviderStatus

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.app_env,
    )


@router.get(
    "/integrations",
    response_model=list[ProviderStatus],
    summary="Integration status",
    description=(
        "Reports which external integrations are live, degraded, or "
        "unconfigured. Use this to tell tested functionality apart from "
        "integrations that are intentionally disabled."
    ),
)
async def integrations(
    settings: Settings = Depends(get_app_settings),
    geography: GeographyService = Depends(get_geography_service),
    google_maps: GoogleMapsAdapter = Depends(get_google_maps_adapter),
) -> list[ProviderStatus]:
    statuses: list[ProviderStatus] = []

    primary = geography.primary
    fallback = geography.fallback

    if primary is not None and primary.name == "countrystatecity":
        statuses.append(
            ProviderStatus(
                name="countrystatecity",
                configured=primary.configured,
                enabled=primary.is_available(),
                reason="configured" if primary.configured else "unconfigured",
                notes=(
                    f"Daily self-imposed budget: {settings.csc_daily_request_limit} "
                    "requests. Falls back to the open dataset when exhausted."
                ),
            )
        )
        if fallback is not None:
            statuses.append(_open_dataset_status(fallback, role="fallback"))
    elif primary is not None and primary.name == "open_dataset":
        statuses.append(
            ProviderStatus(
                name="countrystatecity",
                configured=False,
                enabled=False,
                reason="unconfigured",
                notes=(
                    "No CSC_API_KEY set. Geography is served by the open dataset. "
                    "Set CSC_API_KEY to enable this provider."
                ),
            )
        )
        statuses.append(_open_dataset_status(primary, role="primary"))

    statuses.append(google_maps.status())
    return statuses


def _open_dataset_status(provider: GeographyProvider, *, role: str) -> ProviderStatus:
    built = getattr(provider, "cache_exists", False)
    return ProviderStatus(
        name="open_dataset",
        configured=provider.configured,
        enabled=provider.is_available(),
        reason="configured" if provider.configured else "unconfigured",
        notes=(
            f"Role: {role}. ODbL-1.0 data, no API key or quota. "
            f"Local cache {'present' if built else 'will be built on first request'}."
        ),
    )
