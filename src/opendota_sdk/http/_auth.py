"""Authentication handler for API key injection."""

import os
from typing import Any

# OpenDota reads the key only from `Authorization: Bearer <key>` or an `?api_key=` query
# parameter (svc/web.ts); any other header is silently ignored. The header is used
# rather than the query parameter because a query parameter would put the key into
# every request URL -- and from there into `HTTPStatusError`, which carries the URL.
_AUTH_HEADER = "Authorization"
_AUTH_SCHEME = "Bearer"


class AuthHandler:
    """Injects the OpenDota API key into request headers.

    The key is sent as `Authorization: Bearer <key>`, the only header OpenDota reads. An
    earlier version sent it as `X-API-Key`, which OpenDota ignores without complaint, so
    every keyed request was served as anonymous: 60 requests a minute instead of 300,
    and capped at 3,000 a day.

    Attributes:
        api_key: The API key, or `None` when requests are sent anonymously.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the authentication handler.

        Args:
            api_key: Optional API key. Falls back to the `OPENDOTA_API_KEY` environment
                variable when omitted. Surrounding whitespace is stripped, since a
                trailing newline from a secrets file would make OpenDota reject the
                key's format; a key that is blank after stripping means anonymous.
        """
        key = (api_key or os.getenv("OPENDOTA_API_KEY") or "").strip()
        self.api_key = key or None

    def apply_to_headers(self, headers: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of `headers` carrying the API key, if one is configured.

        A configured key replaces any `Authorization` header already present.

        Args:
            headers: The request headers. Never modified.

        Returns:
            The headers with `Authorization: Bearer <key>` added, or `headers` itself
            when no key is configured.
        """
        if self.api_key:
            headers = dict(headers)
            headers[_AUTH_HEADER] = f"{_AUTH_SCHEME} {self.api_key}"
        return headers

    def has_auth(self) -> bool:
        """Check if an API key is configured.

        Returns:
            True if an API key is set, False otherwise.
        """
        return bool(self.api_key)
