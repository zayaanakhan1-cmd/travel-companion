# Google Maps: why this integration is unconfigured

**Status: intentionally unconfigured. No billing account is enabled. No
billing-dependent API key is used.**

## The requirement

> Google Maps: do not enable billing or use a standard billing-dependent key.
> Use the Demo Key only if officially supported and eligible; otherwise leave
> the adapter unconfigured and document the limitation.

## What the adapter would need

A backend Google Maps adapter for this app would do geocoding and place
search. Both are **Web Service APIs**:

- Geocoding API
- Places API

## What the Demo Key actually supports

Google's Maps Demo Key is the only no-billing credential Google offers. Per
Google's own documentation, it supports a *limited subset* of products:

- Maps JavaScript API (Dynamic Maps)
- Places UI Kit
- Maps Grounding Lite

The Maps Demo Project Terms of Service add further constraints:

1. **Supported APIs** - only a limited subset of Google Maps Platform
   functionality is available. Anything outside that list requires a billing
   account.
2. **No production use** - the Demo Project is "intended solely for evaluation
   and testing. It is not intended for production use. Production use is
   strictly prohibited."
3. **Usage limits** - Google may enforce, adjust, or zero-out the limits at any
   time without notice.
4. **No SLA** - no guarantees regarding uptime, availability, or reliability,
   and no support.

**Web Service APIs are not in the supported set.** So the Demo Key is *not*
officially supported or eligible for the backend adapter this project would
need.

## Conclusion

Under the stated constraints - no billing, no standard billing key - there is
no eligible Google credential for a backend geocoding/places adapter.

Rather than pretend otherwise, the project:

- Ships `backend/app/geography/google_maps.py` as an explicitly inert adapter
  that never issues a request.
- Reports `configured: false, enabled: false, reason: "unconfigured"` from
  `GET /api/v1/integrations`.
- Serves all geography browsing from CountryStateCity and the open dataset.
- Keeps `GOOGLE_MAPS_API_KEY` blank in `.env.example`.

## What would be needed to enable it

To make a backend Google Maps adapter work, someone with the authority to
change the constraints would have to either:

1. **Enable billing** and create a standard API key with the Geocoding and
   Places APIs enabled, then set `GOOGLE_MAPS_API_KEY`. This is the supported
   production path. It is explicitly out of scope here.
2. **Move the integration to the frontend** and use the Maps JavaScript API
   with a Demo Key. That is within the Demo Key's supported set, and a Demo Key
   is a browser credential by design. `frontend/.env.example` reserves
   `VITE_GOOGLE_MAPS_DEMO_KEY` for exactly this. It still carries the
   prototyping-only and daily-limit restrictions, so it is suitable for a demo,
   not a launch.

## Frontend map widget

If a Demo Key is obtained and its terms accepted, the map is rendered entirely
in the browser via the Maps JavaScript API. The key is a public browser
credential; it must never be used for server-side calls. The backend adapter
stays disabled regardless, because the Demo Key cannot serve Web Service
requests.

## Sources

- <https://developers.google.com/maps/demo-key>
- <https://mapsplatform.google.com/maps-demo-key>
- <https://cloud.google.com/terms/maps-platform/demo-project-terms>
