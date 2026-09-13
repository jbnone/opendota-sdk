"""Public client interface for the OpenDota API."""

import asyncio
import logging
from types import TracebackType
from typing import Any, Self

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk.assembler import Assembler
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
        hero_abilities: dict[str, dict[str, Any]],
        abilities: dict[str, dict[str, Any]],
        hero_lore: dict[str, str],
        assembler: Assembler,
    ) -> list[Hero]:
        """Merge hero API data with constants and build typed Hero models."""
        heroes: list[Hero] = []
        for hero in heroes_api:
            hero_id = str(hero["id"])
            if hero_id in heroes_constants:
                merged_hero = {**heroes_constants[hero_id], **hero}
            else:
                logger.warning(
                    f"Hero ID {hero_id} from /heroes not found in /constants/heroes, using API data only"
                )
                merged_hero = dict(hero)

            hero_name = str(hero.get("name", ""))
            hero_ability_data = hero_abilities.get(hero_name)
            if hero_ability_data is None:
                logger.warning(
                    f"Hero name {hero_name!r} not found in /constants/hero_abilities, no abilities/talents"
                )
            else:
                merged_hero["abilities"] = hero_ability_data.get("abilities")
                merged_hero["talents"] = hero_ability_data.get("talents")

            short_name = hero_name.removeprefix("npc_dota_hero_")
            merged_hero["lore"] = hero_lore.get(short_name)

            heroes.append(
                assembler.normalize_hero(merged_hero, abilities_by_name=abilities)
            )

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
        self._assembler = Assembler()

        self._heroes_cache: list[Hero] | None = None
        self._heroes_by_id: dict[int, Hero] = {}
        self._heroes_by_name: dict[str, Hero] = {}
        self._heroes_lock = asyncio.Lock()

        self._items_cache: list[Item] | None = None
        self._items_by_id: dict[int, Item] = {}
        self._items_by_name: dict[str, Item] = {}
        self._items_lock = asyncio.Lock()

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
        """Retrieve info about all Dota 2 heroes as typed models, cached per client."""
        if self._heroes_cache is None:
            async with self._heroes_lock:
                if self._heroes_cache is None:
                    (
                        heroes_api,
                        heroes_constants,
                        hero_abilities,
                        abilities,
                        hero_lore,
                    ) = await asyncio.gather(
                        self._get("/heroes"),
                        self._get("/constants/heroes"),
                        self._get("/constants/hero_abilities"),
                        self._get("/constants/abilities"),
                        self._get("/constants/hero_lore"),
                    )
                    heroes = self.make_heroes(
                        heroes_api=heroes_api,
                        heroes_constants=heroes_constants,
                        hero_abilities=hero_abilities,
                        abilities=abilities,
                        hero_lore=hero_lore,
                        assembler=self._assembler,
                    )
                    self._heroes_by_id = {hero.id: hero for hero in heroes}
                    self._heroes_by_name = {hero.name: hero for hero in heroes}
                    self._heroes_cache = heroes

        return list(self._heroes_cache)

    async def get_hero(
        self, *, hero_id: int | None = None, hero_name: str | None = None
    ) -> Hero | None:
        """Fetch a single hero by id or name, or None if it doesn't exist."""
        if hero_id is None and hero_name is None:
            raise ValueError("Either hero_id or hero_name must be provided.")
        if hero_id is not None and hero_name is not None:
            raise ValueError("Provide either hero_id or hero_name, not both.")

        await self.get_heroes()
        if hero_id is not None:
            return self._heroes_by_id.get(hero_id)
        return self._heroes_by_name.get(hero_name)

    async def get_items(self) -> list[Item]:
        """Fetch all items from the OpenDota constants endpoint, cached per client."""
        if self._items_cache is None:
            async with self._items_lock:
                if self._items_cache is None:
                    items_data = await self._get("/constants/items")
                    raw_items = [
                        {**data, "name": name} for name, data in items_data.items()
                    ]
                    items = self._assembler.list_items(raw_items)
                    self._items_by_id = {item.id: item for item in items}
                    self._items_by_name = {item.name: item for item in items}
                    self._items_cache = items

        return list(self._items_cache)

    async def get_item(
        self, *, item_id: int | None = None, item_name: str | None = None
    ) -> Item | None:
        """Fetch a single item by id or name, or None if it doesn't exist."""
        if item_id is None and item_name is None:
            raise ValueError("Either item_id or item_name must be provided.")
        if item_id is not None and item_name is not None:
            raise ValueError("Provide either item_id or item_name, not both.")

        await self.get_items()
        if item_id is not None:
            return self._items_by_id.get(item_id)
        return self._items_by_name.get(item_name)

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._transport.close()

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit and close the client."""
        await self.close()
