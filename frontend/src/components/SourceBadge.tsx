import type { DataSource } from "../types/api";

/**
 * Renders the required attribution and any provenance notice for a response.
 *
 * Attribution is not optional: the open dataset is ODbL-licensed, which
 * requires it, and the UI should also tell the user when data came from a
 * fallback source rather than the preferred one.
 */
export function SourceBadge({ source }: { source: DataSource }) {
  const providerLabel =
    source.provider === "countrystatecity"
      ? "CountryStateCity"
      : source.provider === "open_dataset"
        ? "Open dataset"
        : "Unavailable";

  return (
    <div className="source-badge">
      <div className="source-badge__row">
        <span className="source-badge__provider">{providerLabel}</span>
        {source.cached && <span className="pill">cached</span>}
        {source.fallbackUsed && <span className="pill pill--warn">fallback</span>}
        {source.license && <span className="pill">{source.license}</span>}
      </div>
      <p className="source-badge__attribution">{source.attribution}</p>
      {source.notice && <p className="source-badge__notice">{source.notice}</p>}
    </div>
  );
}
