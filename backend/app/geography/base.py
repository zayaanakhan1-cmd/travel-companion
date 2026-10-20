"""Geography provider abstraction.

A provider knows how to fetch countries, states and cities from one upstream
source and normalise the result into the models in `app.schemas`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas import City, Country, DataSource, StateRegion


class GeographyProvider(ABC):
    """Common interface for every geography data source."""

    #: Stable identifier, also used in the `source.provider` field.
    name: str

    @property
    @abstractmethod
    def configured(self) -> bool:
        """True when this provider has everything it needs to run."""

    @abstractmethod
    def is_available(self) -> bool:
        """True when this provider can serve a request right now."""

    @abstractmethod
    async def list_countries(self) -> tuple[list[Country], DataSource]:
        ...

    @abstractmethod
    async def list_states(self, country_iso2: str) -> tuple[list[StateRegion], DataSource]:
        ...

    @abstractmethod
    async def list_cities(
        self, country_iso2: str, state_iso2: str
    ) -> tuple[list[City], DataSource]:
        ...
