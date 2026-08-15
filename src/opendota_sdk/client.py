"""Public client interface for the OpenDota API."""

import logging
from typing import Any

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk.assembler import Assembler
from opendota_sdk.constants import ConstantsRegistry
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import AsyncHTTPTransport
from opendota_sdk.models import Hero, Item

logger = logging.getLogger(__name__)


class ClientLogicMixin:
    """Mixin for client logic shared by async client flows."""

    def make_heroes(
        self,
        *,
        heroes_api: list[dict[str, Any]],
        heroes_constants: dict[str, dict[str, Any]],
    ) -> list[Hero]:
        """Merge hero API data with constants and build typed Hero models."""
        heroes: list[Hero] = []
        for hero in heroes_api:
            hero_id = str(hero["id"])
            if hero_id in heroes_constants:
                merged_hero = {**heroes_constants[hero_id], **hero}
                heroes.append(Hero(**merged_hero))
            else:
                logger.warning(
                    f"Hero ID {hero_id} from /heroes not found in /constants/heroes, using API data only"
                )
                heroes.append(Hero(**hero))

        return heroes


class OpenDotaAsyncClient(ClientLogicMixin):
    """Asynchronous client for the OpenDota API."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        base_url: str | None = None,
        config: OpenDotaClientConfig | None = None,
    ) -> None:
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
        self._constants = ConstantsRegistry(self._transport)
        self._assembler = Assembler()

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make an internal HTTP request and return decoded JSON."""
        return await self._transport.request_json(
            method="GET",
            path=path,
            params=params,
            json_body=json_body,
            **kwargs,
        )

    async def get_heroes(self) -> list[Hero]:
        """Retrieve info about all Dota 2 heroes as typed models."""
        heroes_api: list[dict[str, Any]] = await self._get("/heroes")
        heroes_constants: dict[str, dict[str, Any]] = await self._get(
            "/constants/heroes"
        )
        return self.make_heroes(
            heroes_api=heroes_api, heroes_constants=heroes_constants
        )

    async def get_items(self) -> list[Item]:
        """Fetch all items from the OpenDota constants endpoint."""
        raw_items = await self._constants.get_items()
        return self._assembler.list_items(raw_items)

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._transport.close()

    async def __aenter__(self) -> "OpenDotaAsyncClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit and close the client."""
        await self.close()
