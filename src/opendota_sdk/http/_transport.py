"""HTTP transport layer for OpenDota API requests."""

import asyncio
import json
import logging
import math
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import urljoin

import niquests
from tenacity import RetryCallState

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._errors import (
    HTTPStatusError,
    InvalidAPIKeyError,
    RateLimitError,
    ResponseDecodeError,
    TransportError,
)

from ._auth import AuthHandler
from ._retry import RetryPolicy, build_retry_decorator, is_retryable_rate_limit

_DEFAULT_HEADERS = {"Accept": "application/json"}

logger = logging.getLogger(__name__)

# Query parameters whose values must never reach a log line. OpenDota accepts the API
# key as `?api_key=`, so a request built that way would otherwise leak it.
_REDACTED_PARAMS = frozenset({"api_key"})


def _log_target(path: str, params: dict[str, Any] | None) -> str:
    """Render a request for log lines: the API-relative path and redacted params.

    Deliberately not the full URL and never headers, which is where the API key lives.
    """
    if not params:
        return path
    shown = "&".join(
        f"{key}={'***' if key.lower() in _REDACTED_PARAMS else value}"
        for key, value in params.items()
    )
    return f"{path}?{shown}"


def _rejected_key_reason(response: niquests.Response) -> str | None:
    """Return OpenDota's reason if this response rejects the API key, else `None`.

    OpenDota signals a bad key only as HTTP 400 with a JSON `error` naming the API key
    ("Invalid API key format", or "API key invalid. ..." for unknown or cancelled keys),
    so that body is the only reliable marker. Any other 400 is left as `HTTPStatusError`.
    """
    if response.status_code != 400:
        return None
    try:
        body = json.loads(response.text or "")
    except (TypeError, ValueError):
        return None
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, str) and "api key" in error.lower():
        return error
    return None


def _describe_failure(exc: BaseException | None) -> str:
    """Summarize a failed attempt for a log line without echoing response bodies."""
    if isinstance(exc, RateLimitError):
        return "daily rate limit" if exc.is_daily_limit else "rate limit (HTTP 429)"
    if isinstance(exc, HTTPStatusError):
        return f"HTTP {exc.status_code}"
    if isinstance(exc, TransportError):
        return "timeout" if exc.is_timeout else "connection error"
    return type(exc).__name__ if exc is not None else "unknown failure"


# OpenDota's per-minute counter is a fixed window that resets at every wall-clock
# minute boundary on the server (svc/web.ts expires it at the start of the next
# minute). It never sends Retry-After, so that boundary is the wait to honor.
_MINUTE_WINDOW_SECONDS = 60
# The Date header only resolves to the second and the counter expires on a different
# machine's clock; one extra second keeps a retry from landing just before the reset.
_WINDOW_RESET_MARGIN_SECONDS = 1


def _parse_int(value: str | None) -> int | None:
    """Parse an integer header value, or return `None` if absent or malformed."""
    if value is None:
        return None
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return None


def _parse_http_date(value: str | None) -> datetime | None:
    """Parse an HTTP-date header value into an aware UTC datetime."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_retry_after(value: str | None, server_date: datetime | None) -> int | None:
    """Parse `Retry-After` as delta-seconds or an HTTP-date, per RFC 9110.

    An HTTP-date is measured against the server's own `Date` when available, so
    client clock skew cannot stretch or shrink the wait.
    """
    if value is None:
        return None
    seconds = _parse_int(value)
    if seconds is not None:
        return max(0, seconds)
    retry_at = _parse_http_date(value)
    if retry_at is None:
        return None
    now = server_date or datetime.now(UTC)
    return max(0, math.ceil((retry_at - now).total_seconds()))


def _rate_limit_details(headers: Mapping[str, str]) -> tuple[int | None, bool]:
    """Work out how long a 429 asks the client to wait, and whether it is the daily cap.

    Precedence: an exhausted daily quota (keyless requests only) cannot be waited out,
    so it wins outright; then an explicit `Retry-After`, which OpenDota itself never
    sends but a proxy in front of it may; then OpenDota's own minute window, recognized
    by its negative `X-Rate-Limit-Remaining-Minute` header. Anything else is a 429 of
    unknown origin, left to ordinary exponential backoff.

    Args:
        headers: The 429 response's headers, in any key case.

    Returns:
        `(retry_after, is_daily_limit)`; `retry_after` is `None` when no wait is known.
    """
    lowered = {key.lower(): value for key, value in headers.items()}

    remaining_day = _parse_int(lowered.get("x-rate-limit-remaining-day"))
    if remaining_day is not None and remaining_day < 0:
        return None, True

    server_date = _parse_http_date(lowered.get("date"))

    retry_after = _parse_retry_after(lowered.get("retry-after"), server_date)
    if retry_after is not None:
        return retry_after, False

    remaining_minute = _parse_int(lowered.get("x-rate-limit-remaining-minute"))
    if remaining_minute is not None and remaining_minute < 0:
        now = server_date or datetime.now(UTC)
        return (
            _MINUTE_WINDOW_SECONDS - now.second + _WINDOW_RESET_MARGIN_SECONDS,
            False,
        )

    return None, False


class HTTPTransportBase:
    """Base class for HTTP transports.

    Defines the URL, header, and response-handling behavior shared by transports.
    `AsyncHTTPTransport` is the only subclass; the SDK is async-only.
    """

    def __init__(
        self,
        config: OpenDotaClientConfig,
        auth_handler: AuthHandler,
        retry_policy: RetryPolicy,
    ) -> None:
        """Initialize the transport.

        Args:
            config: The client configuration.
            auth_handler: Authentication handler for API key injection.
            retry_policy: Policy for retrying failed requests.
        """
        self.config = config
        self.auth_handler = auth_handler
        self.retry_policy = retry_policy
        self._retry_decorator = build_retry_decorator(retry_policy)

    def build_url(self, path: str) -> str:
        """Build full URL from base URL and path.

        Args:
            path: The API path (e.g., "/heroStats").

        Returns:
            The full URL.
        """
        base_url = self.config.base_url
        if base_url:
            # Ensure base URL ends with a slash for proper urljoin behavior
            sanitized_base_url = base_url if base_url.endswith("/") else base_url + "/"
        else:
            sanitized_base_url = ""

        return urljoin(sanitized_base_url, path.lstrip("/"))

    def build_headers(
        self, request_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Build request headers by merging defaults, config, and extra headers.

        Args:
            request_headers: Additional headers to include in this request. They
                override both the defaults and the config's `extra_headers`.

        Returns:
            The merged headers dictionary.
        """
        merged_headers = _DEFAULT_HEADERS.copy()
        merged_headers.update(self.config.extra_headers or {})
        if request_headers:
            merged_headers.update(request_headers)

        return self.auth_handler.apply_to_headers(merged_headers)

    def handle_response(
        self, response: niquests.Response, method: str
    ) -> niquests.Response:
        """Validate response status and raise errors if needed.

        Args:
            response: The HTTP response.
            method: The HTTP method used.

        Returns:
            The response if valid.

        Raises:
            RateLimitError: If rate limited (429).
            HTTPStatusError: For other error status codes.
        """
        if response.status_code == 429:
            retry_after, is_daily_limit = _rate_limit_details(response.headers)
            scope = "Daily request limit exceeded" if is_daily_limit else "Rate limited"
            raise RateLimitError(
                retry_after=retry_after,
                message=f"{scope} on {method} {response.url}",
                is_daily_limit=is_daily_limit,
            )

        if not response.ok:
            # Only a request that carried a key can have it rejected; the check keeps an
            # unrelated 400 that happens to mention an API key from being misreported.
            reason = (
                _rejected_key_reason(response) if self.auth_handler.has_auth() else None
            )
            if reason is not None:
                raise InvalidAPIKeyError(
                    reason=reason,
                    status_code=response.status_code,
                    method=method,
                    url=response.url,
                    response_text=response.text,
                    headers=dict(response.headers),
                )
            raise HTTPStatusError(
                status_code=response.status_code,
                method=method,
                url=response.url,
                response_text=response.text,
                headers=dict(response.headers),
            )

        return response


class AsyncHTTPTransport(HTTPTransportBase):
    """Asynchronous HTTP transport using niquests.

    Handles request execution, retries, rate limiting, and API key authentication
    for asynchronous operations.

    This is an internal transport implementation. It is not part of the public API
    and should not be used directly by end users.
    """

    def __init__(
        self,
        config: OpenDotaClientConfig,
        auth_handler: AuthHandler,
        retry_policy: RetryPolicy,
    ) -> None:
        """Initialize the async transport.

        Args:
            config: The client configuration.
            auth_handler: Authentication handler for API key injection.
            retry_policy: Policy for retrying failed requests.

        Raises:
            ValueError: If `config.max_concurrency` is below 1, which would block every
                request forever.
        """
        super().__init__(config, auth_handler, retry_policy)
        if config.max_concurrency < 1:
            raise ValueError(
                f"max_concurrency must be at least 1, got {config.max_concurrency}."
            )
        self._session = niquests.AsyncSession()
        # Bounds requests in flight. An attempt holds its slot while it waits out any
        # rate-limit cooldown and while it is on the wire; exponential backoff between
        # attempts happens outside it, so a retry that is merely backing off never
        # starves other requests.
        self._slots = asyncio.Semaphore(config.max_concurrency)
        # Monotonic time before which no request may be sent. Shared across the client
        # because OpenDota counts per API key or IP: once one request is told to back
        # off, every other request from this client would be rejected too.
        self._resume_at = 0.0
        # The one clock and sleep for every wait the transport takes -- rate-limit
        # cooldowns and retry backoff alike -- so tests can drive both without really
        # waiting.
        self._clock: Callable[[], float] = time.monotonic
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

    async def _wait_for_cooldown(self, method: str, target: str) -> None:
        """Sleep until any rate-limit cooldown has passed.

        Loops because another request may extend the cooldown while this one sleeps.
        """
        while (remaining := self._resume_at - self._clock()) > 0:
            logger.debug(
                "%s %s: waiting %.1fs for the rate-limit cooldown",
                method,
                target,
                remaining,
            )
            await self._sleep(remaining)

    def _start_cooldown(self, exc: RateLimitError, method: str, target: str) -> None:
        """Hold every request on this client until the rate limit clears.

        Only for 429s that will actually be retried: a daily cap, an over-long wait, or
        a policy that does not retry 429s fails fast instead of stalling other requests.
        Logged only when the deadline actually moves, so a burst of concurrent 429s
        reports one pause rather than one line per rejected request.
        """
        if exc.retry_after is None or not is_retryable_rate_limit(
            self.retry_policy, exc
        ):
            return
        resume_at = self._clock() + exc.retry_after
        if resume_at > self._resume_at:
            logger.info(
                "Rate limited on %s %s; holding all requests on this client for %ds",
                method,
                target,
                exc.retry_after,
            )
            self._resume_at = resume_at

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> niquests.Response:
        """Make an HTTP request.

        Args:
            method: HTTP method.
            path: API path.
            params: Query parameters.
            json_body: JSON body for POST/PUT.
            data: Form data.
            headers: Additional headers.
            timeout: Request timeout in seconds.

        Returns:
            The HTTP response.

        Raises:
            HTTPStatusError: For error status codes.
            TransportError: For connection/timeout errors.
            RateLimitError: For rate limit errors.
        """
        target = _log_target(path, params)
        attempt = 0

        def _log_retry(retry_state: RetryCallState) -> None:
            outcome = retry_state.outcome
            exc = (
                outcome.exception() if outcome is not None and outcome.failed else None
            )
            if isinstance(exc, RateLimitError) and exc.retry_after is not None:
                logger.info(
                    "Retrying %s %s after %s (attempt %d of %d) once the limit clears",
                    method,
                    target,
                    _describe_failure(exc),
                    retry_state.attempt_number,
                    self.retry_policy.max_retries,
                )
                return
            next_action = retry_state.next_action
            logger.info(
                "Retrying %s %s after %s (attempt %d of %d) in %.2fs",
                method,
                target,
                _describe_failure(exc),
                retry_state.attempt_number,
                self.retry_policy.max_retries,
                next_action.sleep if next_action is not None else 0.0,
            )

        async def _do_request() -> niquests.Response:
            nonlocal attempt
            attempt += 1
            async with self._slots:
                await self._wait_for_cooldown(method, target)
                started = self._clock()
                try:
                    response = await self._session.request(
                        method=method,
                        url=self.build_url(path),
                        params=params or None,
                        json=json_body,
                        data=data,
                        headers=self.build_headers(headers),
                        timeout=timeout or self.config.timeout,
                        verify=self.config.verify_ssl,
                    )
                    logger.debug(
                        "%s %s -> %d in %.2fs (attempt %d)",
                        method,
                        target,
                        response.status_code,
                        self._clock() - started,
                        attempt,
                    )
                    return self.handle_response(response, method)
                except niquests.Timeout as exc:
                    logger.debug(
                        "%s %s timed out after %.2fs (attempt %d)",
                        method,
                        target,
                        self._clock() - started,
                        attempt,
                    )
                    raise TransportError(
                        f"Request timed out: {exc}", is_timeout=True
                    ) from exc
                except (
                    niquests.RequestException,
                    niquests.ConnectionError,
                ) as exc:
                    logger.debug(
                        "%s %s failed after %.2fs (attempt %d): %s",
                        method,
                        target,
                        self._clock() - started,
                        attempt,
                        type(exc).__name__,
                    )
                    raise TransportError(f"Request failed: {exc}") from exc
                except RateLimitError as exc:
                    self._start_cooldown(exc, method, target)
                    raise
                except HTTPStatusError:
                    raise

        try:
            return await self._retry_decorator.copy(
                sleep=self._sleep, before_sleep=_log_retry
            )(_do_request)
        except Exception as exc:
            if isinstance(exc, (RateLimitError, HTTPStatusError, TransportError)):
                raise
            raise TransportError(f"Unexpected error: {exc}") from exc

    async def request_json(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Make a request and return decoded JSON.

        Args:
            method: HTTP method.
            path: API path.
            params: Query parameters.
            json_body: JSON body.
            data: Form data.
            headers: Additional headers.
            timeout: Request timeout.

        Returns:
            The decoded JSON response body.

        Raises:
            HTTPStatusError: For error status codes.
            TransportError: For connection errors.
            ResponseDecodeError: If JSON decoding fails.
        """
        response = await self.request(
            method=method,
            path=path,
            params=params,
            json_body=json_body,
            data=data,
            headers=headers,
            timeout=timeout,
        )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise ResponseDecodeError(
                f"Failed to decode JSON from {response.url}: {exc}"
            ) from exc

    async def request_bytes(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> bytes:
        """Make a request and return raw bytes.

        Args:
            method: HTTP method.
            path: API path.
            params: Query parameters.
            json_body: JSON body.
            data: Form data.
            headers: Additional headers.
            timeout: Request timeout.

        Returns:
            The raw response body as bytes.
        """
        response = await self.request(
            method=method,
            path=path,
            params=params,
            json_body=json_body,
            data=data,
            headers=headers,
            timeout=timeout,
        )
        return response.content or b""

    async def close(self) -> None:
        """Close the session and clean up resources."""
        if self._session is not None:
            await self._session.close()

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit and close the session."""
        await self.close()
