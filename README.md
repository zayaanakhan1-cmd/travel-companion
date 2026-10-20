# Travel Companion

A travel companion app with a FastAPI backend and a React frontend. The backend
owns all external credentials and serves geography data (countries, regions,
cities) over a documented HTTP contract; the frontend renders it and never
touches a provider key.

```
travel-companion/
├── backend/            FastAPI service (geography, quota, fallback, tests)
│   ├── app/
│   │   ├── geography/  providers, validation, quota, dataset builder
│   │   ├── routers/    HTTP endpoints
│   │   ├── config.py   settings and secrets
│   │   └── main.py     app factory
│   ├── data/           generated SQLite cache (git-ignored)
│   └── tests/          109 tests
├── frontend/           React + TypeScript + Vite
│   └── src/
│       ├── api/        typed client for the backend contract
│       ├── components/ geography browser, attribution badge
│       └── types/      contract types
└── docs/               API contracts, Google Maps decision
```

## Quick start

### Backend

```bash
cd backend
python -m venv ../.venv
../.venv/bin/pip install -e ".[dev]"

# Optional: pre-build the geography cache (~22 MB, one download).
../.venv/bin/python -m app.geography

../.venv/bin/python -m uvicorn app.main:app --reload
```

Serves on <http://127.0.0.1:8000>. Interactive docs at `/docs`.

If you skip the pre-build step, the cache is built automatically on the first
geography request (`OPEN_DATASET_AUTO_BUILD=true`, the default).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Serves on <http://127.0.0.1:5173>. The Vite dev server proxies `/api` to
`http://127.0.0.1:8000`, so no backend URL or CORS configuration is needed
during development.

## Configuration

Copy `.env.example` to `.env` and fill in only what you need. Every setting has
a working default; the app runs with **no secrets at all** on the open dataset.

| Variable | Default | Purpose |
|----------|---------|---------|
| `GEOGRAPHY_PROVIDER` | `auto` | `auto`, `countrystatecity`, or `open_dataset`. |
| `CSC_API_KEY` | *(blank)* | CountryStateCity key. Optional. |
| `CSC_DAILY_REQUEST_LIMIT` | `100` | Self-imposed daily cap on CSC calls. |
| `OPEN_DATASET_CACHE_PATH` | `backend/data/csc.sqlite3` | Where the cache is written. |
| `OPEN_DATASET_AUTO_BUILD` | `true` | Build the cache on first use. |
| `GOOGLE_MAPS_API_KEY` | *(blank)* | Intentionally blank. See below. |
| `CORS_ALLOW_ORIGINS` | localhost:5173 | Browser origins allowed to call the API. |

**Never commit `.env`.** It is in `.gitignore`, and `.env.example` documents the
shape without holding a value.

## Geography data

Two providers, one contract.

| | CountryStateCity | Open dataset |
|---|---|---|
| Cost | Free tier, metered | Free, unlimited |
| Key required | Yes | No |
| Quota | ~100 req/day (free tier) | None |
| Query-time network | Yes | No (local SQLite) |
| Licence | CSC terms | ODbL-1.0 |
| Role | Preferred when configured | Fallback and default |

**Open dataset.** The genuinely free path. `app.geography.dataset_builder`
downloads the pinned release of
[countries-states-cities-database](https://github.com/dr5hn/countries-states-cities-database)
(ODbL-1.0), projects the fields the API exposes, and writes a compact SQLite
cache (~22 MB) with indexes. 250 countries, 5,327 regions, 152,375 cities.

**Attribution is required.** ODbL requires credit, so every response carries a
`source.attribution` string and the UI renders it. Do not remove it.

**Fallback.** When CountryStateCity is unconfigured, rate-limited, or erroring,
the service serves from the open dataset and sets `source.fallback_used = true`
with an explanatory `source.notice`. A `400` from validation is never masked by
a fallback, and a `404` stays a `404` rather than becoming a `503`.

## Google Maps

**Not configured, deliberately.** A backend adapter needs the Geocoding or
Places Web Service APIs. The no-billing Maps Demo Key does not support Web
Service APIs, and is licensed for prototyping only. Enabling a backend adapter
would require billing, which this project has not enabled.

`GET /api/v1/integrations` reports it as `unconfigured`, and the adapter never
issues a request. Full reasoning: [`docs/google-maps.md`](docs/google-maps.md).

## API

Base path `/api/v1`. Full reference: [`docs/api-contracts.md`](docs/api-contracts.md).

```
GET /api/v1/health
GET /api/v1/integrations
GET /api/v1/geography/countries
GET /api/v1/geography/countries/{country_iso2}/states
GET /api/v1/geography/countries/{country_iso2}/states/{state_iso2}/cities
```

Every geography response is `{ data, source }`. Every error is
`{ error: { code, detail } }`.

## Tests

```bash
cd backend
../.venv/bin/python -m pytest -q
```

109 tests, no mocks for the code under test: the open-dataset tests run real SQL
against a real SQLite cache built by the production builder, and the
CountryStateCity tests run against a real local HTTP server that speaks the
upstream contract.

Coverage includes input validation (including injection attempts), the rolling
quota window, provider fallback and provenance, the HTTP contract end to end,
and secret hygiene (no key appears in any response body).

```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run build       # production bundle
```

## Security notes

- **No secret in source control.** `.env` is ignored; `.env.example` holds no values.
- **Secrets are server-side only.** Only the backend reads provider keys.
- **Redaction is enforced.** A logging filter scrubs configured secrets from
  every record, and token-shaped strings are redacted even if unconfigured.
- **Errors are opaque.** Upstream messages are never forwarded, and rejected
  input is never echoed back, so a key cannot surface through an error.
- **Input is validated before use.** Identifiers are checked against a strict
  allow-list before reaching an HTTP client or a SQL query.
- **The remote URL carries no credential.** Authentication uses the `gh` git
  credential helper, which stores the token outside the repository.

## Roadmap

- Phase B (this change): geography integration, complete and tested.
- Next: trip planning on top of the geography contract, against
  `frontend/src/api/client.ts`.
- Blocked pending a policy decision: any Google Maps feature. See
  [`docs/google-maps.md`](docs/google-maps.md).