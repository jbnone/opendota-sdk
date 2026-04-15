"""OpenDota SDK exception hierarchy and error types."""

from typing import Any


class OpenDotaError(Exception):
    """Base exception for all OpenDota SDK errors."""

    pass


class TransportError(OpenDotaError):
    """Raised when a transport-level error occurs (connection, timeout, etc.)."""

    pass


class HTTPStatusError(OpenDotaError):
    """Raised when an HTTP response indicates an error status code.

    Attributes:
        status_code: The HTTP status code returned by the server.
        method: The HTTP method used in the request.
        url: The URL that was requested.
        response_text: The response body as text.
        headers: The response headers.
    """

    def __init__(
        self,
        status_code: int | None,
        method: str,
        url: str | None,
        response_text: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Initialize HTTPStatusError.

        Args:
            status_code: The HTTP status code returned by the server.
            method: The HTTP method used in the request.
            url: The URL that was requested.
            response_text: The response body as text (optional).
            headers: The response headers (optional).
        """
        self.status_code = status_code
        self.method = method
        self.url = url
        self.response_text = response_text
        self.headers = headers or {}
        message = f"{method} {url}: {status_code}"
        if response_text:
            truncated = (
                response_text[:100] + "..."
                if len(response_text) > 100
                else response_text
            )
            message += f"\n{truncated}"
        super().__init__(message)


class RateLimitError(OpenDotaError):
    """Raised when the API rate limit is exceeded (HTTP 429).

    Attributes:
        retry_after: The number of seconds to wait before retrying, if provided.
        message: A descriptive error message.
    """

    def __init__(self, retry_after: int | None = None, message: str = "") -> None:
        """Initialize RateLimitError.

        Args:
            retry_after: The number of seconds to wait before retrying (optional).
            message: A descriptive error message (optional).
        """
        self.retry_after = retry_after
        if not message:
            if retry_after:
                message = f"Rate limited. Retry after {retry_after} seconds."
            else:
                message = "Rate limited."
        super().__init__(message)


class ResponseDecodeError(OpenDotaError):
    """Raised when response body cannot be decoded (e.g., invalid JSON)."""

    pass
