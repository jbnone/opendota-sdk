"""Public client interface for the OpenDota API."""

import asyncio
import logging
from types import TracebackType
from typing import Any, Self

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._context import bind_client, unbind_client
from opendota_sdk.assembler import Assembler
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import AsyncHTTPTransport
from opendota_sdk.models import Hero, HeroStats, Item

logger = logging.getLogger(__name__)


class OpenDotaAsyncClient:
    """Asynchronous client for the OpenDota API.

    The client owns all HTTP access, caching, and payload normalization. Every `get_*`
    method returns typed models rather than raw dictionaries, and the bulk fetches
    (`get_heroes()`, `get_items()`, `get_hero_stats()`) are cached per client instance
    and single-flighted, so concurrent calls collapse to one request.

    Entering the client as an async context manager also binds it as the active client
    for model relationship methods such as `Hero.get_stats()`; use `activate()` /
    `deactivate()` for the same effect outside `async with`.

    Example:
        ```python
        async with OpenDotaAsyncClient() as client:
            hero = await client.get_hero(hero_name="npc_dota_hero_antimage")
            stats = await hero.get_stats()
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
        """Create a client, either from keyword arguments or a full config object.

        Args:
            api_key: OpenDota API key. Falls back to the `OPENDOTA_API_KEY` environment
                variable when omitted.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for failed requests.
            base_url: API base URL. Defaults to the public OpenDota API.
            config: A complete `OpenDotaClientConfig`. When given, it is used as-is and
                the other arguments are ignored.
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
        self._assembler = Assembler()

        self._heroes_cache: list[Hero] | None = None
        self._heroes_by_id: dict[int, Hero] = {}
        self._heroes_by_name: dict[str, Hero] = {}
        self._heroes_lock = asyncio.Lock()

        self._items_cache: list[Item] | None = None
        self._items_by_id: dict[int, Item] = {}
        self._items_by_name: dict[str, Item] = {}
        self._items_lock = asyncio.Lock()

        self._hero_stats_cache: list[HeroStats] | None = None
        self._hero_stats_by_id: dict[int, HeroStats] = {}
        self._hero_stats_by_name: dict[str, HeroStats] = {}
        self._hero_stats_lock = asyncio.Lock()

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

    @staticmethod
    def _make_heroes(
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

    async def get_heroes(self) -> list[Hero]:
        """Fetch every hero as a typed `Hero`, cached per client.

        The first call fetches `/heroes` and the hero-related constants concurrently and
        merges them; later calls return the cached result without hitting the network.

        Returns:
            A fresh list of all heroes. Mutating the list does not affect the cache.

        Raises:
            OpenDotaError: If a request fails or a hero payload cannot be normalized.
        """
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
                    heroes = self._make_heroes(
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
        """Look up a single hero by id or internal name.

        Populates the hero cache via `get_heroes()` if needed, then resolves from an index.

        Args:
            hero_id: Numeric hero id.
            hero_name: Internal hero name (e.g. `"npc_dota_hero_antimage"`).

        Returns:
            The matching hero, or `None` if no hero has that id or name.

        Raises:
            ValueError: If neither or both of `hero_id` and `hero_name` are given.
            OpenDotaError: If the underlying `get_heroes()` fetch fails.
        """
        if hero_id is None and hero_name is None:
            raise ValueError("Either hero_id or hero_name must be provided.")
        if hero_id is not None and hero_name is not None:
            raise ValueError("Provide either hero_id or hero_name, not both.")

        await self.get_heroes()
        if hero_id is not None:
            return self._heroes_by_id.get(hero_id)
        return self._heroes_by_name.get(hero_name)

    async def get_hero_stats(self) -> list[HeroStats]:
        """Fetch live pick/win statistics for every hero, cached per client.

        `/heroStats` is aggregate data that changes over time, but it is still cached so
        that concurrent per-hero lookups collapse to one request. Create a new client to
        observe fresh numbers.

        Returns:
            A fresh list of statistics for all heroes. Mutating the list does not affect
            the cache.

        Raises:
            OpenDotaError: If the request fails or an entry cannot be normalized.
        """
        if self._hero_stats_cache is None:
            async with self._hero_stats_lock:
                if self._hero_stats_cache is None:
                    raw_stats = await self._get("/heroStats")
                    stats = self._assembler.list_hero_stats(raw_stats)
                    self._hero_stats_by_id = {stat.hero_id: stat for stat in stats}
                    self._hero_stats_by_name = {stat.hero_name: stat for stat in stats}
                    self._hero_stats_cache = stats

        return list(self._hero_stats_cache)

    async def get_hero_stat(
        self, *, hero_id: int | None = None, hero_name: str | None = None
    ) -> HeroStats | None:
        """Look up a single hero's live statistics by id or internal name.

        Populates the stats cache via `get_hero_stats()` if needed, then resolves from an
        index. This is what `Hero.get_stats()` delegates to.

        Args:
            hero_id: Numeric hero id.
            hero_name: Internal hero name (e.g. `"npc_dota_hero_antimage"`).

        Returns:
            The matching statistics, or `None` if `/heroStats` has no entry for the hero.

        Raises:
            ValueError: If neither or both of `hero_id` and `hero_name` are given.
            OpenDotaError: If the underlying `get_hero_stats()` fetch fails.
        """
        if hero_id is None and hero_name is None:
            raise ValueError("Either hero_id or hero_name must be provided.")
        if hero_id is not None and hero_name is not None:
            raise ValueError("Provide either hero_id or hero_name, not both.")

        await self.get_hero_stats()
        if hero_id is not None:
            return self._hero_stats_by_id.get(hero_id)
        return self._hero_stats_by_name.get(hero_name)

    async def get_items(self) -> list[Item]:
        """Fetch every item as a typed `Item`, cached per client.

        The first call fetches `/constants/items`; later calls return the cached result
        without hitting the network.

        Returns:
            A fresh list of all items. Mutating the list does not affect the cache.

        Raises:
            OpenDotaError: If the request fails or an item payload cannot be normalized.
        """
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
        """Look up a single item by id or internal name.

        Populates the item cache via `get_items()` if needed, then resolves from an index.

        Args:
            item_id: Numeric item id.
            item_name: Internal item name (e.g. `"blink"`).

        Returns:
            The matching item, or `None` if no item has that id or name.

        Raises:
            ValueError: If neither or both of `item_id` and `item_name` are given.
            OpenDotaError: If the underlying `get_items()` fetch fails.
        """
        if item_id is None and item_name is None:
            raise ValueError("Either item_id or item_name must be provided.")
        if item_id is not None and item_name is not None:
            raise ValueError("Provide either item_id or item_name, not both.")

        await self.get_items()
        if item_id is not None:
            return self._items_by_id.get(item_id)
        return self._items_by_name.get(item_name)

    def activate(self) -> None:
        """Bind this client as the active client for the current context.

        Equivalent to what `async with` does on entry, for scripts and notebooks that
        cannot use a context manager. Pair with `deactivate()`.
        """
        bind_client(self)

    def deactivate(self) -> None:
        """Undo the most recent `activate()` in the current context.

        Restores whichever client (if any) was active before. Does nothing if this
        context has no active binding.
        """
        unbind_client()

    async def close(self) -> None:
        """Close the underlying HTTP transport and release its connections.

        Called automatically on `async with` exit. The client must not be used afterwards.
        """
        await self._transport.close()

    async def __aenter__(self) -> Self:
        """Enter the client scope, binding it as the active client.

        Returns:
            This client.
        """
        bind_client(self)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the client scope: unbind the active client and close the transport."""
        unbind_client()
        await self.close()
