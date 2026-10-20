"""Domain exceptions and their HTTP mapping.

Every error response carries a machine-readable `code` and a `detail` string
that is safe to show a user. Upstream provider messages are deliberately not
forwarded verbatim, so an API key can never surface in an error body.
"""

from __future__ import annotations


class GeographyError(Exception):
    """Base class for geography failures."""

    code = "geography_error"
    http_status = 500

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class InvalidCountryCodeError(GeographyError):
    code = "invalid_country_code"
    http_status = 400


class InvalidStateCodeError(GeographyError):
    code = "invalid_state_code"
    http_status = 400


class NotFoundError(GeographyError):
    code = "not_found"
    http_status = 404


class ProviderUnavailableError(GeographyError):
    """Raised when no provider can serve the request."""

    code = "provider_unavailable"
    http_status = 503


class ProviderAuthError(GeographyError):
    """The provider rejected our credentials."""

    code = "provider_auth_error"
    http_status = 502


class ProviderRateLimitedError(GeographyError):
    """The provider refused the request because a quota was exhausted."""

    code = "provider_rate_limited"
    http_status = 429


class ProviderUpstreamError(GeographyError):
    """The provider returned an unexpected response."""

    code = "provider_upstream_error"
    http_status = 502
