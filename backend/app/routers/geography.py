"""Geography browsing endpoints - the Phase B contract.

Contract summary (see docs/api-contracts.md for the full reference):

  GET /api/v1/geography/countries
      -> { data: Country[], source: DataSource }

  GET /api/v1/geography/countries/{country_iso2}/states
      -> { data: StateRegion[], source: DataSource }

  GET /api/v1/geography/countries/{country_iso2}/states/{state_iso2}/cities
      -> { data: City[], source: DataSource }

Every response includes `source`, which carries attribution and whether the
fallback provider was used. Errors use the shape
`{ "error": { "code": ..., "detail": ... } }`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.dependencies import get_geography_service
from app.geography.service import GeographyService
from app.schemas import (
    CityListResponse,
    CountryListResponse,
    StateListResponse,
)

router = APIRouter(prefix="/geography", tags=["geography"])

_COUNTRY_PATH = Path(
    ...,
    description="ISO 3166-1 alpha-2 country code, e.g. 'IN'.",
    min_length=2,
    max_length=2,
    examples=["IN"],
)
_STATE_PATH = Path(
    ...,
    description="Subdivision code as returned by the states endpoint, e.g. 'MH'.",
    min_length=1,
    max_length=6,
    examples=["MH"],
)


@router.get(
    "/countries",
    response_model=CountryListResponse,
    summary="List countries",
)
async def list_countries(
    geography: GeographyService = Depends(get_geography_service),
) -> CountryListResponse:
    data, source = await geography.list_countries()
    return CountryListResponse(data=data, source=source)


@router.get(
    "/countries/{country_iso2}/states",
    response_model=StateListResponse,
    summary="List states/regions for a country",
)
async def list_states(
    country_iso2: str = _COUNTRY_PATH,
    geography: GeographyService = Depends(get_geography_service),
) -> StateListResponse:
    data, source = await geography.list_states(country_iso2)
    return StateListResponse(data=data, source=source)


@router.get(
    "/countries/{country_iso2}/states/{state_iso2}/cities",
    response_model=CityListResponse,
    summary="List cities for a state/region",
    description=(
        "City coverage varies by country and by provider. Some subdivisions "
        "have no city records; that is reported as 404 with a clear message "
        "rather than an empty list, so the UI can distinguish 'none known' "
        "from 'not found'."
    ),
)
async def list_cities(
    country_iso2: str = _COUNTRY_PATH,
    state_iso2: str = _STATE_PATH,
    geography: GeographyService = Depends(get_geography_service),
) -> CityListResponse:
    data, source = await geography.list_cities(country_iso2, state_iso2)
    return CityListResponse(data=data, source=source)
