# API contracts

Base URL: `/api/v1`. Interactive docs: `/docs` (OpenAPI at `/openapi.json`).

All responses are JSON. Field names are `snake_case`, matching the Pydantic
models in `backend/app/schemas.py`. The frontend maps them to `camelCase` at
the client boundary (`frontend/src/api/client.ts`).

---

## Conventions

### Success envelope

Every geography response has the same two keys:

```json
{
  "data": [ ... ],
  "source": { ... }
}
```

`source` is **not optional**. It carries the attribution the data licence
requires, plus provenance flags the UI needs to be honest with the user.

### Error envelope

Every error, from any endpoint, looks like this:

```json
{
  "error": {
    "code": "invalid_country_code",
    "detail": "Country code must be a two-letter ISO 3166-1 alpha-2 code, e.g. 'IN'."
  }
}
```

`code` is stable and safe to branch on. `detail` is user-safe prose. Neither
ever contains a provider API key or the raw upstream response.

### Error codes

| HTTP | `code` | Meaning |
|------|--------|---------|
| 400 | `invalid_country_code` | The country code is not two ASCII letters. |
| 400 | `invalid_state_code` | The state code is not 1-6 alphanumerics. |
| 404 | `not_found` | No record for that path. Includes "country with no subdivisions" and "state with no cities". |
| 422 | `validation_error` | A path/query parameter failed FastAPI validation. |
| 429 | `provider_rate_limited` | A provider's quota is exhausted. Normally handled internally by falling back. |
| 502 | `provider_auth_error` | The provider rejected our credentials. |
| 502 | `provider_upstream_error` | The provider returned an unexpected response. |
| 503 | `provider_unavailable` | No provider could serve the request at all. |
| 500 | `internal_error` | Unexpected server fault. Detail is deliberately opaque. |

Note: a `404` is a definitive answer about the *request*, not an outage. If
both the primary and fallback provider report "no such record", the client
still receives `404`, not `503`.

---

## `GET /api/v1/health`

Liveness probe. Never touches a provider.

```json
{ "status": "ok", "version": "0.1.0", "environment": "development" }
```

---

## `GET /api/v1/integrations`

Reports the state of each external integration. Use this to distinguish
**tested, working functionality** from **integrations that are intentionally
unconfigured**.

```json
[
  {
    "name": "countrystatecity",
    "configured": false,
    "enabled": false,
    "reason": "unconfigured",
    "notes": "No CSC_API_KEY set. Geography is served by the open dataset..."
  },
  {
    "name": "open_dataset",
    "configured": true,
    "enabled": true,
    "reason": "configured",
    "notes": "Role: primary. ODbL-1.0 data, no API key or quota. Local cache present."
  },
  {
    "name": "google_maps",
    "configured": false,
    "enabled": false,
    "reason": "unconfigured",
    "notes": "Google Maps is not configured..."
  }
]
```

---

## `GET /api/v1/geography/countries`

All countries, sorted by name.

```json
{
  "data": [
    {
      "iso2": "IN",
      "iso3": "IND",
      "name": "India",
      "native_name": "भारत",
      "capital": "New Delhi",
      "region": "Asia",
      "subregion": "Southern Asia",
      "currency": "INR",
      "phonecode": "91",
      "latitude": 20.0,
      "longitude": 77.0,
      "emoji": "🇮🇳"
    }
  ],
  "source": {
    "provider": "open_dataset",
    "attribution": "Data source: countries-states-cities-database (ODbL-1.0), https://github.com/dr5hn/countries-states-cities-database",
    "license": "ODbL-1.0",
    "cached": true,
    "fallback_used": false,
    "notice": null
  }
}
```

---

## `GET /api/v1/geography/countries/{country_iso2}/states`

States, provinces, and regions for one country.

- `country_iso2`: ISO 3166-1 alpha-2, case-insensitive. `in` and `IN` are equivalent.
- Response `data` is sorted by name.
- Returns `404` if the country is unknown.

```json
{
  "data": [
    {
      "iso2": "MH",
      "name": "Maharashtra",
      "native_name": null,
      "type": "state",
      "country_iso2": "IN",
      "latitude": 19.7514798,
      "longitude": 75.7138884,
      "timezone": "Asia/Kolkata"
    }
  ],
  "source": { "...": "..." }
}
```

> **Contract note on `iso2`.** Pass this value straight back as `state_iso2` in
> the cities endpoint. Its exact meaning is provider-dependent (CountryStateCity
> state code vs. ISO 3166-2 without the country prefix), which is why the UI must
> treat it as an opaque token from this endpoint rather than constructing it.
> It can be `null` for some subdivisions; such entries have no city listing.

---

## `GET /api/v1/geography/countries/{country_iso2}/states/{state_iso2}/cities`

Cities within a state/region.

- Both codes are case-insensitive.
- Response `data` is sorted by name.
- Returns `404` when the state is unknown **or** when it is known but has no
  city records. The `detail` distinguishes the two cases.

```json
{
  "data": [
    {
      "name": "Mumbai",
      "native_name": null,
      "country_iso2": "IN",
      "state_iso2": "MH",
      "state_name": null,
      "latitude": 19.07283,
      "longitude": 72.88261,
      "timezone": "Asia/Kolkata"
    }
  ],
  "source": { "...": "..." }
}
```

### City coverage caveat

City coverage is uneven in every public dataset. Some subdivisions have no
cities at all. The API reports that as `404` with an explanatory `detail`
rather than an empty `200`, so the UI can tell "none known" apart from "the
request was wrong".

---

## Data source semantics

| Field | Meaning |
|-------|---------|
| `provider` | Which source answered: `countrystatecity`, `open_dataset`, or `unavailable`. |
| `attribution` | Required credit line. **Render this wherever the data appears.** |
| `license` | Licence identifier when known (`ODbL-1.0`, or the CSC terms). |
| `cached` | `true` when served from the local dataset cache. |
| `fallback_used` | `true` when the preferred provider failed and a fallback answered. |
| `notice` | Present when data is degraded or came from a fallback. |

### Provider selection

Configured by `GEOGRAPHY_PROVIDER` (`auto`, `countrystatecity`, `open_dataset`):

- `auto` (default) - CountryStateCity when `CSC_API_KEY` is set, else the open dataset.
- `countrystatecity` - prefer the hosted API; fall back to the open dataset on
  failure or quota exhaustion.
- `open_dataset` - open dataset only. No network at query time, no quota.

In every mode the response is identical in shape. Only `source` changes.
