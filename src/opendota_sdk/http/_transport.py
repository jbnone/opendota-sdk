"""HTTP transport layer for OpenDota API requests."""

import json
from typing import Any
from urllib.parse import urljoin

import niquests

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._errors import (
    HTTPStatusError,
    RateLimitError,
    ResponseDecodeError,
    TransportError,
)

from ._auth import AuthHandler
from ._retry import RetryPolicy, build_retry_decorator


class _SyncHTTPTransport:
    """Synchronous HTTP transport using niquests.

    Handles request execution, retries, rate limiting, and API key authentication
    for synchronous operations.
    """

    def __init__(
        self,
        config: OpenDotaClientConfig,
        auth_handler: AuthHandler,
        retry_policy: RetryPolicy,
    ) -> None:
        """Initialize the sync transport.

        Args:
            config: The client configuration.
            auth_handler: Authentication handler for API key injection.
            retry_policy: Policy for retrying failed requests.
        """
        self.config = config
        self.auth_handler = auth_handler
        self.retry_policy = retry_policy
        self._session = niquests.Session()
        self._retry_decorator = build_retry_decorator(retry_policy)

    def _build_url(self, path: str) -> str:
        """Build full URL from base URL and path.

        Args:
            path: The API path (e.g., "/heroStats").

        Returns:
            The full URL.
        """
        return urljoin(self.config.base_url, path.lstrip("/"))

    def _handle_response(
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
            retry_after = None
            if "Retry-After" in response.headers:
                try:
                    retry_after = int(response.headers["Retry-After"])
                except (ValueError, TypeError):
                    pass
            raise RateLimitError(
                retry_after=retry_after,
                message=f"Rate limited on {method} {response.url}",
            )

        if not response.ok:
            raise HTTPStatusError(
                status_code=response.status_code,
                method=method,
                url=response.url,
                response_text=response.text,
                headers=dict(response.headers),
            )

        return response

    def request(
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
        url = self._build_url(path)
        timeout = timeout or self.config.timeout
        merged_headers = dict(self.config.default_headers or {})
        if headers:
            merged_headers.update(headers)
        merged_headers = self.auth_handler.apply_to_headers(merged_headers)
        merged_params = dict(params or {})
        merged_params = self.auth_handler.apply_to_params(merged_params)

        def _do_request() -> niquests.Response:
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    params=merged_params or None,
                    json=json_body,
                    data=data,
                    headers=merged_headers,
                    timeout=timeout,
                    verify=self.config.verify_ssl,
                )
                return self._handle_response(response, method)
            except (
                niquests.RequestException,
                niquests.ConnectionError,
                niquests.Timeout,
            ) as exc:
                raise TransportError(f"Request failed: {exc}") from exc
            except RateLimitError:
                raise
            except HTTPStatusError:
                raise

        try:
            return self._retry_decorator(_do_request)
        except Exception as exc:
            if isinstance(exc, (RateLimitError, HTTPStatusError, TransportError)):
                raise
            raise TransportError(f"Unexpected error: {exc}") from exc

    def request_json(
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
        response = self.request(
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

    def request_bytes(
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
        response = self.request(
            method=method,
            path=path,
            params=params,
            json_body=json_body,
            data=data,
            headers=headers,
            timeout=timeout,
        )
        return response.content or b""

    def close(self) -> None:
        """Close the session and clean up resources."""
        self._session.close()

    def __enter__(self) -> "_SyncHTTPTransport":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and close the session."""
        self.close()


class _AsyncHTTPTransport:
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
        """
        self.config = config
        self.auth_handler = auth_handler
        self.retry_policy = retry_policy
        self._session: niquests.AsyncSession | None = None
        self._retry_decorator = build_retry_decorator(retry_policy)

    async def _ensure_session(self) -> niquests.AsyncSession:
        """Lazily create and return the async session.

        Returns:
            The async session instance.
        """
        if self._session is None:
            self._session = niquests.AsyncSession()
        return self._session

    def _build_url(self, path: str) -> str:
        """Build full URL from base URL and path.

        Args:
            path: The API path (e.g., "/heroStats").

        Returns:
            The full URL.
        """
        return urljoin(self.config.base_url, path.lstrip("/"))

    def _handle_response(
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
            retry_after = None
            if "Retry-After" in response.headers:
                try:
                    retry_after = int(response.headers["Retry-After"])
                except (ValueError, TypeError):
                    pass
            raise RateLimitError(
                retry_after=retry_after,
                message=f"Rate limited on {method} {response.url}",
            )

        if not response.ok:
            raise HTTPStatusError(
                status_code=response.status_code,
                method=method,
                url=response.url,
                response_text=response.text,
                headers=dict(response.headers),
            )

        return response

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
        session = await self._ensure_session()
        url = self._build_url(path)
        timeout = timeout or self.config.timeout
        merged_headers = dict(self.config.default_headers or {})
        if headers:
            merged_headers.update(headers)
        merged_headers = self.auth_handler.apply_to_headers(merged_headers)
        merged_params = dict(params or {})
        merged_params = self.auth_handler.apply_to_params(merged_params)

        async def _do_request() -> niquests.Response:
            try:
                response = await session.request(
                    method=method,
                    url=url,
                    params=merged_params or None,
                    json=json_body,
                    data=data,
                    headers=merged_headers,
                    timeout=timeout,
                    verify=self.config.verify_ssl,
                )
                return self._handle_response(response, method)
            except (
                niquests.RequestException,
                niquests.ConnectionError,
                niquests.Timeout,
            ) as exc:
                raise TransportError(f"Request failed: {exc}") from exc
            except RateLimitError:
                raise
            except HTTPStatusError:
                raise

        try:
            return await self._retry_decorator(_do_request)
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

    async def __aenter__(self) -> "_AsyncHTTPTransport":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit and close the session."""
        await self.close()
