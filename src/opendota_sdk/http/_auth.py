"""Authentication handler for API key injection."""

import os
from typing import Any


class AuthHandler:
    """Handles API key authentication by injecting credentials into requests.

    Supports injection via HTTP headers (default) or query parameters.

    Attributes:
        api_key: The API key for authentication.
        header_name: The header name for API key injection (e.g., "X-API-Key").
    """

    def __init__(
        self,
        api_key: str | None = None,
        header_name: str = "X-API-Key",
    ) -> None:
        """Initialize the authentication handler.

        Args:
            api_key: Optional API key. If not provided, reads from OPENDOTA_API_KEY
                environment variable.
            header_name: The HTTP header name for API key injection.
        """
        self.api_key = api_key or os.getenv("OPENDOTA_API_KEY")
        self.header_name = header_name

    def apply_to_headers(self, headers: dict[str, Any]) -> dict[str, Any]:
        """Inject API key into request headers.

        Args:
            headers: The headers dictionary to modify.

        Returns:
            The modified headers dictionary with API key injected (if available).
        """
        if self.api_key:
            headers = dict(headers)
            headers[self.header_name] = self.api_key
        return headers

    def has_auth(self) -> bool:
        """Check if an API key is configured.

        Returns:
            True if an API key is set, False otherwise.
        """
        return bool(self.api_key)
