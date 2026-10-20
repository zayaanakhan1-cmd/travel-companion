/**
 * Typed client for the Travel Companion API.
 *
 * The frontend never talks to a geography provider directly and never holds a
 * provider API key. Everything goes through the backend, which owns the
 * credentials, the quota, and the fallback logic.
 *
 * Note on field names: the backend serialises Pydantic models with
 * `snake_case` keys. Responses are mapped to the camelCase shapes in
 * `types/api.ts` at this boundary, so the rest of the UI never sees a raw
 * payload.
 */

import type {
  ApiErrorBody,
  CityListResponse,
  CountryListResponse,
  ProviderStatus,
  StateListResponse,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

/** An error carrying the backend's machine-readable code. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, detail: string, status: number) {
    super(detail);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null) return false;
  const candidate = (value as { error?: unknown }).error;
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    typeof (candidate as { code?: unknown }).code === "string"
  );
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json" },
    });
  } catch {
    // Network-level failure: no response at all.
    throw new ApiError("network_error", "Could not reach the server.", 0);
  }

  const raw: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (isErrorBody(raw)) {
      throw new ApiError(raw.error.code, raw.error.detail, response.status);
    }
    throw new ApiError("unexpected_error", "The server returned an error.", response.status);
  }
  return raw as T;
}

/** The backend uses snake_case; the UI uses camelCase. */
function mapSource(raw: Record<string, unknown>) {
  return {
    provider: raw.provider as CountryListResponse["source"]["provider"],
    attribution: raw.attribution as string,
    license: (raw.license ?? null) as string | null,
    cached: Boolean(raw.cached),
    fallbackUsed: Boolean(raw.fallback_used),
    notice: (raw.notice ?? null) as string | null,
  };
}

export async function fetchCountries(): Promise<CountryListResponse> {
  const raw = await request<{ data: Record<string, unknown>[]; source: Record<string, unknown> }>(
    "/geography/countries",
  );
  return {
    data: raw.data.map((c) => ({
      iso2: c.iso2 as string,
      iso3: (c.iso3 ?? null) as string | null,
      name: c.name as string,
      nativeName: (c.native_name ?? null) as string | null,
      capital: (c.capital ?? null) as string | null,
      region: (c.region ?? null) as string | null,
      subregion: (c.subregion ?? null) as string | null,
      currency: (c.currency ?? null) as string | null,
      phonecode: (c.phonecode ?? null) as string | null,
      latitude: (c.latitude ?? null) as number | null,
      longitude: (c.longitude ?? null) as number | null,
      emoji: (c.emoji ?? null) as string | null,
    })),
    source: mapSource(raw.source),
  };
}

export async function fetchStates(countryIso2: string): Promise<StateListResponse> {
  const raw = await request<{ data: Record<string, unknown>[]; source: Record<string, unknown> }>(
    `/geography/countries/${encodeURIComponent(countryIso2)}/states`,
  );
  return {
    data: raw.data.map((s) => ({
      iso2: (s.iso2 ?? null) as string | null,
      name: s.name as string,
      nativeName: (s.native_name ?? null) as string | null,
      type: (s.type ?? null) as string | null,
      countryIso2: s.country_iso2 as string,
      latitude: (s.latitude ?? null) as number | null,
      longitude: (s.longitude ?? null) as number | null,
      timezone: (s.timezone ?? null) as string | null,
    })),
    source: mapSource(raw.source),
  };
}

export async function fetchCities(
  countryIso2: string,
  stateIso2: string,
): Promise<CityListResponse> {
  const raw = await request<{ data: Record<string, unknown>[]; source: Record<string, unknown> }>(
    `/geography/countries/${encodeURIComponent(countryIso2)}/states/${encodeURIComponent(
      stateIso2,
    )}/cities`,
  );
  return {
    data: raw.data.map((c) => ({
      name: c.name as string,
      nativeName: (c.native_name ?? null) as string | null,
      countryIso2: c.country_iso2 as string,
      stateIso2: (c.state_iso2 ?? null) as string | null,
      stateName: (c.state_name ?? null) as string | null,
      latitude: (c.latitude ?? null) as number | null,
      longitude: (c.longitude ?? null) as number | null,
      timezone: (c.timezone ?? null) as string | null,
    })),
    source: mapSource(raw.source),
  };
}

export async function fetchIntegrations(): Promise<ProviderStatus[]> {
  return request<ProviderStatus[]>("/integrations");
}
