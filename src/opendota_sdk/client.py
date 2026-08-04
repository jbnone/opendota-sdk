"""Domain-oriented client interface for the OpenDota API."""

from opendota_sdk import Item

from typing import Any

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk.assembler import Assembler
from opendota_sdk.constants import ConstantsRegistry
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import AsyncHTTPTransport


class OpenDotaAsyncClient:
    """Async OpenDota client exposing domain resources."""

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
        self.constants = ConstantsRegistry(self._transport)
        self._assembler = Assembler()

    async def get_items(self) -> list[Item]:
        """Fetch all items from the OpenDota constants endpoint."""
        raw_items = await self.constants.get_items()
        items = []
        for raw_item in raw_items:
            item = self._assembler.normalize_item(raw_item)
            items.append(item)
        return items

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> "OpenDotaAsyncClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
