"""Public client interface for the OpenDota API."""

import logging
from typing import Any

from opendota_sdk._config import OpenDotaClientConfig, config_from_env, default_config
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import AsyncHTTPTransport, SyncHTTPTransport
from opendota_sdk.responses import HeroesResponse

logger = logging.getLogger(__name__)


class ClientLogicMixin:
    """Mixin for client logic that can be shared between sync and async clients."""

    def make_heroes_response(
        self,
        *,
        heroes_api: list[dict[str, Any]],
        heroes_constants: dict[str, dict[str, Any]],
    ) -> HeroesResponse:
        """Updates hero data from the constants  with the data from /heroes and return a HeroesResponse."""
        heroes: list[dict[str, Any]] = []
        for hero in heroes_api:
            hero_id = str(hero["id"])
            if hero_id in heroes_constants:
                merged_hero = {**heroes_constants[hero_id], **hero}
                heroes.append(merged_hero)
            else:
                logger.warning(
                    f"Hero ID {hero_id} from /heroes not found in /constants/heroes, using API data only"
                )
                heroes.append(hero)

        return HeroesResponse(heroes)


class OpenDotaClient(ClientLogicMixin):
    """Synchronous client for the OpenDota API.

    Provides high-level, ergonomic access to OpenDota API endpoints with
    automatic retry handling, rate-limit management, and API key authentication.

    Example:
        ```python
        from opendota_sdk import OpenDotaClient

        # Zero-config usage
        client = OpenDotaClient()
        heroes = client.get_heroes()

        # With API key
        client = OpenDotaClient(api_key="my-key")
        heroes = client.get_heroes()

        # Context manager for resource management
        with OpenDotaClient() as client:
            heroes = client.get_heroes()
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        base_url: str | None = None,
        config: OpenDotaClientConfig | None = None,
    ) -> None:
        """Initialize the OpenDota client.

        Args:
            api_key: Optional API key for authentication. If not provided, checks
                OPENDOTA_API_KEY environment variable.
            timeout: Request timeout in seconds (default: 10.0).
            max_retries: Maximum number of retries for failed requests (default: 3).
            base_url: Optional base URL for the API (default: https://api.opendota.com/api).
            config: Optional OpenDotaClientConfig for advanced customization.
                If provided, overrides all other arguments.
        """
        config_from_args = OpenDotaClientConfig(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        if base_url:
            config_from_args.base_url = base_url

        if config is None:
            defaults = default_config()
            self._config = defaults.merge_other(config_from_env()).merge_other(
                config_from_args
            )
        else:
            self._config = config

        self._auth_handler = AuthHandler(api_key=self._config.api_key)
        self._retry_policy = RetryPolicy(
            max_retries=self._config.max_retries,
            backoff_factor=self._config.backoff_factor,
            retry_on_status=self._config.retry_on_status,
        )
        self._transport = SyncHTTPTransport(
            config=self._config,
            auth_handler=self._auth_handler,
            retry_policy=self._retry_policy,
        )

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make an internal HTTP request and return decoded JSON.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path (e.g., "/heroStats").
            params: Query parameters.
            json_body: JSON request body.
            **kwargs: Additional arguments passed to transport.

        Returns:
            The decoded JSON response body.
        """
        return self._transport.request_json(
            method="GET",
            path=path,
            params=params,
            json_body=json_body,
            **kwargs,
        )

    def get_heroes(self) -> HeroesResponse:
        """Retrieve info about all Dota 2 heroes.

        Returns:
            A HeroesResponse containing a list of hero data.

        Raises:
            OpenDotaError: For any API-related errors, including HTTP errors, rate limits, and decoding issues.
        """
        heroes_api: list[dict[str, Any]] = self._get("/heroes")
        heroes_constants: dict[str, dict[str, Any]] = self._get("/constants/heroes")
        return self.make_heroes_response(
            heroes_api=heroes_api, heroes_constants=heroes_constants
        )

    def close(self) -> None:
        """Close the client and release resources."""
        self._transport.close()

    def __enter__(self) -> "OpenDotaClient":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and close the client."""
        self.close()


class OpenDotaAsyncClient(ClientLogicMixin):
    """Asynchronous client for the OpenDota API.

    Provides high-level, ergonomic access to OpenDota API endpoints with
    automatic retry handling, rate-limit management, and API key authentication.
    All operations are async and must be awaited.

    Example:
        ```python
        import asyncio
        from opendota_sdk import OpenDotaAsyncClient

        async def main():
            # Zero-config usage
            async with OpenDotaAsyncClient() as client:
                heroes = await client.get_heroes()
                print(f"Loaded {len(heroes)} heroes")

        asyncio.run(main())
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        base_url: str | None = None,
        config: OpenDotaClientConfig | None = None,
    ) -> None:
        """Initialize the async OpenDota client.

        Args:
            api_key: Optional API key for authentication. If not provided, checks
                OPENDOTA_API_KEY environment variable.
            timeout: Request timeout in seconds (default: 10.0).
            max_retries: Maximum number of retries for failed requests (default: 3).
            base_url: Optional base URL for the API (default: https://api.opendota.com/api).
            config: Optional OpenDotaClientConfig for advanced customization.
                If provided, overrides all other arguments.
        """
        if config is None:
            config = OpenDotaClientConfig(
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
                base_url=base_url or "https://api.opendota.com/api",
            )

        self._config = config
        self._auth_handler = AuthHandler(api_key=config.api_key)
        self._retry_policy = RetryPolicy(
            max_retries=config.max_retries,
            backoff_factor=config.backoff_factor,
            retry_on_status=config.retry_on_status,
        )
        self._transport = AsyncHTTPTransport(
            config=config,
            auth_handler=self._auth_handler,
            retry_policy=self._retry_policy,
        )

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make an internal HTTP request and return decoded JSON.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path (e.g., "/heroStats").
            params: Query parameters.
            json_body: JSON request body.
            **kwargs: Additional arguments passed to transport.

        Returns:
            The decoded JSON response body.
        """
        return await self._transport.request_json(
            method="GET",
            path=path,
            params=params,
            json_body=json_body,
            **kwargs,
        )

    async def get_heroes(self) -> HeroesResponse:
        """Retrieve info about all Dota 2 heroes.

        Returns:
            A HeroesResponse containing a list of hero data.

        Raises:
            OpenDotaError: For any API-related errors, including HTTP errors, rate limits, and decoding issues.
        """
        heroes_api: list[dict[str, Any]] = await self._get("/heroes")
        heroes_constants: dict[str, dict[str, Any]] = await self._get(
            "/constants/heroes"
        )
        return self.make_heroes_response(
            heroes_api=heroes_api, heroes_constants=heroes_constants
        )

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._transport.close()

    async def __aenter__(self) -> "OpenDotaAsyncClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit and close the client."""
        await self.close()
