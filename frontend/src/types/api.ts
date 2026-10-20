/**
 * Types mirroring the backend contract in `backend/app/schemas.py`.
 *
 * These are hand-maintained rather than generated, so that a backend change
 * that is not reflected here is a visible diff rather than a silent drift.
 * Keep them in sync with `docs/api-contracts.md`.
 */

export type ProviderName = "countrystatecity" | "open_dataset" | "unavailable";

export interface DataSource {
  provider: ProviderName;
  /** Required attribution text. Render this wherever data is displayed. */
  attribution: string;
  license: string | null;
  cached: boolean;
  /** True when the preferred provider failed and a fallback served the data. */
  fallbackUsed: boolean;
  notice: string | null;
}

export interface Country {
  iso2: string;
  iso3: string | null;
  name: string;
  nativeName: string | null;
  capital: string | null;
  region: string | null;
  subregion: string | null;
  currency: string | null;
  phonecode: string | null;
  latitude: number | null;
  longitude: number | null;
  emoji: string | null;
}

export interface StateRegion {
  iso2: string | null;
  name: string;
  nativeName: string | null;
  type: string | null;
  countryIso2: string;
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
}

export interface City {
  name: string;
  nativeName: string | null;
  countryIso2: string;
  stateIso2: string | null;
  stateName: string | null;
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
}

export interface CountryListResponse {
  data: Country[];
  source: DataSource;
}

export interface StateListResponse {
  data: StateRegion[];
  source: DataSource;
}

export interface CityListResponse {
  data: City[];
  source: DataSource;
}

export interface ProviderStatus {
  name: string;
  configured: boolean;
  enabled: boolean;
  reason: string;
  notes: string | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    detail: string;
  };
}
