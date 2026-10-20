"""Google Maps adapter - intentionally unconfigured.

Decision (see docs/google-maps.md for the full write-up):

The travel companion would use Google for geocoding and place search, both of
which are *Web Service* APIs. The Google Maps "Demo Key" - the only no-billing
key Google offers - is officially supported for a limited product set (Maps
JavaScript API / Dynamic Maps, Places UI Kit, Maps Grounding Lite). Web Service
APIs are not in that set, and the Maps Demo Project terms explicitly prohibit
production use.

The task constraints are: do not enable billing, and do not use a
billing-dependent standard key. Under those constraints there is no eligible
Google credential for a backend geocoding adapter. So this module reports
`configured=False` and the API surfaces that as `unconfigured`, rather than
pretending the integration works or silently mocking responses.

If a Google Maps Demo Key is later obtained for the *frontend* map widget, it
is a browser credential and belongs in the frontend env (`VITE_GOOGLE_MAPS_DEMO_KEY`),
not here.
"""

from __future__ import annotations

from app.schemas import ProviderStatus

#: Products a backend adapter would need, none of which the Demo Key covers.
REQUIRED_WEB_SERVICE_APIS = ("Geocoding API", "Places API")

LIMITATION = (
    "Google Maps is not configured. A backend adapter needs a Web Service API "
    "(Geocoding / Places), which the no-billing Maps Demo Key does not support. "
    "Enabling it would require billing, which this project has deliberately not "
    "enabled. Geography browsing is served by CountryStateCity and the open "
    "dataset instead."
)


class GoogleMapsAdapter:
    """Placeholder adapter that never performs a request."""

    name = "google_maps"

    def __init__(self, *, api_key: str = "") -> None:
        self._api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def enabled(self) -> bool:
        # Deliberately always False: even with a key, a Demo Key cannot call
        # the Web Service APIs this adapter would need.
        return False

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            configured=self.configured,
            enabled=self.enabled,
            reason="unconfigured",
            notes=LIMITATION,
        )
