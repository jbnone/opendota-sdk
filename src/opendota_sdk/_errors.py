"""OpenDota SDK exception hierarchy and error types."""

from typing import Any


class OpenDotaError(Exception):
    """Base exception for all OpenDota SDK errors."""


class TransportError(OpenDotaError):
    """Raised when a transport-level error occurs (connection, timeout, etc.).

    Attributes:
        is_timeout: `True` when the underlying failure was a request timeout rather
            than another transport-level failure. Retries consult this to honor
            `RetryPolicy.retry_on_timeout`.
    """

    def __init__(self, message: str = "", *, is_timeout: bool = False) -> None:
        """Initialize TransportError.

        Args:
            message: A descriptive error message.
            is_timeout: Whether the underlying failure was a request timeout.
        """
        self.is_timeout = is_timeout
        super().__init__(message)


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


class InvalidAPIKeyError(HTTPStatusError):
    """Raised when OpenDota rejects the configured API key.

    OpenDota answers HTTP 400 both for a key that is not well formed and for one it does
    not recognize (unknown or cancelled). Either way no request can succeed until the key
    is fixed or removed, so this is never retried. It subclasses `HTTPStatusError`, so code
    that already catches that still catches this.

    Attributes:
        reason: OpenDota's own explanation, e.g. `"Invalid API key format"`.
    """

    def __init__(
        self,
        reason: str,
        status_code: int | None,
        method: str,
        url: str | None,
        response_text: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """Initialize InvalidAPIKeyError.

        Args:
            reason: OpenDota's explanation of why the key was rejected.
            status_code: The HTTP status code returned by the server.
            method: The HTTP method used in the request.
            url: The URL that was requested.
            response_text: The response body as text (optional).
            headers: The response headers (optional).
        """
        super().__init__(status_code, method, url, response_text, headers)
        self.reason = reason
        message = (
            f"OpenDota rejected the API key ({reason.rstrip('. ')}). Check the "
            "`api_key` argument or the OPENDOTA_API_KEY environment variable, or "
            "remove the key to send requests anonymously."
        )
        self.args = (message,)


class RateLimitError(OpenDotaError):
    """Raised when the API rate limit is exceeded (HTTP 429).

    Attributes:
        retry_after: Seconds to wait before the limit clears, or `None` when the
            response gives no way to tell. Taken from a `Retry-After` header when one
            is sent; otherwise, for OpenDota's per-minute limit, it is the time left
            until the next minute begins on the server's clock.
        is_daily_limit: `True` when the daily request quota (keyless requests only)
            is exhausted rather than the per-minute one. Waiting a minute will not
            help, so these are never retried.
        message: A descriptive error message.
    """

    def __init__(
        self,
        retry_after: int | None = None,
        message: str = "",
        *,
        is_daily_limit: bool = False,
    ) -> None:
        """Initialize RateLimitError.

        Args:
            retry_after: The number of seconds to wait before retrying (optional).
            message: A descriptive error message (optional).
            is_daily_limit: Whether the daily quota, not the per-minute one, was hit.
        """
        self.retry_after = retry_after
        self.is_daily_limit = is_daily_limit
        if not message:
            if is_daily_limit:
                message = "Daily request limit exceeded."
            elif retry_after:
                message = f"Rate limited. Retry after {retry_after} seconds."
            else:
                message = "Rate limited."
        super().__init__(message)


class ResponseDecodeError(OpenDotaError):
    """Raised when response body cannot be decoded (e.g., invalid JSON)."""
