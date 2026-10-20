import { useEffect, useState } from "react";
import { ApiError, fetchCities, fetchCountries, fetchStates } from "../api/client";
import type { City, Country, DataSource, StateRegion } from "../types/api";
import { SourceBadge } from "./SourceBadge";

/**
 * Three-level geography browser: country -> state/region -> city.
 *
 * This is the reference implementation of the Phase B contract. Mujtaba can
 * build the trip-planning UI on top of `src/api/client.ts` without touching
 * anything in this component.
 */
export function GeographyBrowser() {
  const [countries, setCountries] = useState<Country[]>([]);
  const [states, setStates] = useState<StateRegion[]>([]);
  const [cities, setCities] = useState<City[]>([]);

  const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);
  const [selectedState, setSelectedState] = useState<StateRegion | null>(null);

  const [source, setSource] = useState<DataSource | null>(null);
  const [loading, setLoading] = useState<"countries" | "states" | "cities" | null>("countries");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCountries()
      .then((response) => {
        if (cancelled) return;
        setCountries(response.data);
        setSource(response.source);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSelectCountry(country: Country) {
    setSelectedCountry(country);
    setSelectedState(null);
    setCities([]);
    setError(null);
    setLoading("states");
    try {
      const response = await fetchStates(country.iso2);
      setStates(response.data);
      setSource(response.source);
    } catch (err) {
      setStates([]);
      setError(describeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function onSelectState(state: StateRegion) {
    setSelectedState(state);
    setCities([]);
    setError(null);
    setLoading("cities");
    try {
      const response = await fetchCities(state.countryIso2, state.iso2 ?? "");
      setCities(response.data);
      setSource(response.source);
    } catch (err) {
      setCities([]);
      setError(describeError(err));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="browser">
      <header className="browser__header">
        <h1>Travel Companion</h1>
        <p className="browser__subtitle">
          Browse countries, regions, and cities. Geography data is served by the
          backend; no provider keys reach the browser.
        </p>
      </header>

      {error && (
        <div className="alert" role="alert">
          <strong>Could not load data.</strong> {error}
        </div>
      )}

      <div className="browser__columns">
        <Column
          title="Countries"
          count={countries.length}
          loading={loading === "countries"}
          emptyMessage="No countries returned."
        >
          {countries.map((country) => (
            <button
              key={country.iso2}
              type="button"
              className={`item ${selectedCountry?.iso2 === country.iso2 ? "item--active" : ""}`}
              onClick={() => void onSelectCountry(country)}
            >
              <span className="item__emoji">{country.emoji ?? "🌐"}</span>
              <span className="item__name">{country.name}</span>
              <span className="item__meta">{country.iso2}</span>
            </button>
          ))}
        </Column>

        <Column
          title={selectedCountry ? `Regions in ${selectedCountry.name}` : "Regions"}
          count={states.length}
          loading={loading === "states"}
          emptyMessage={
            selectedCountry
              ? "No regions reported for this country."
              : "Select a country to see its regions."
          }
        >
          {states.map((state) => (
            <button
              key={`${state.countryIso2}-${state.iso2 ?? state.name}`}
              type="button"
              className={`item ${selectedState?.name === state.name ? "item--active" : ""}`}
              onClick={() => void onSelectState(state)}
            >
              <span className="item__name">{state.name}</span>
              {state.type && <span className="item__meta">{state.type}</span>}
            </button>
          ))}
        </Column>

        <Column
          title={selectedState ? `Cities in ${selectedState.name}` : "Cities"}
          count={cities.length}
          loading={loading === "cities"}
          emptyMessage={
            selectedState
              ? "No cities reported for this region."
              : "Select a region to see its cities."
          }
        >
          {cities.map((city) => (
            <div key={`${city.name}-${city.latitude ?? "x"}-${city.longitude ?? "y"}`} className="item item--static">
              <span className="item__name">{city.name}</span>
              {city.timezone && <span className="item__meta">{city.timezone}</span>}
            </div>
          ))}
        </Column>
      </div>

      {source && <SourceBadge source={source} />}
    </div>
  );
}

function Column({
  title,
  count,
  loading,
  emptyMessage,
  children,
}: {
  title: string;
  count: number;
  loading: boolean;
  emptyMessage: string;
  children: React.ReactNode;
}) {
  return (
    <section className="column">
      <h2 className="column__title">
        {title} {count > 0 && <span className="column__count">{count}</span>}
      </h2>
      <div className="column__body">
        {loading ? (
          <p className="column__empty">Loading…</p>
        ) : count === 0 ? (
          <p className="column__empty">{emptyMessage}</p>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    // The backend supplies a user-safe message; codes let the UI branch.
    return err.message;
  }
  return "An unexpected error occurred.";
}
