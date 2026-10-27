"""Public client interface for the OpenDota API."""

import asyncio
import logging
import time
from types import TracebackType
from typing import Any, Self

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._context import bind_client, unbind_client
from opendota_sdk.assembler import Assembler
from opendota_sdk.enums import HeroName, ItemName
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import AsyncHTTPTransport
from opendota_sdk.models import (
    Hero,
    HeroBenchmarks,
    HeroItemPopularity,
    HeroMatchups,
    HeroStats,
    Item,
)

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
            hero = await client.get_hero(HeroName.ANTI_MAGE)
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
        max_concurrency: int = 10,
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
            max_concurrency: Maximum number of requests in flight at once.

        Raises:
            ValueError: If `max_concurrency` (or the config's) is below 1.
        """
        if config is None:
            config = OpenDotaClientConfig(
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
                base_url=base_url or "https://api.opendota.com/api",
                max_concurrency=max_concurrency,
            )

        self._config = config
        self._auth_handler = AuthHandler(api_key=config.api_key)
        self._retry_policy = RetryPolicy(
            max_retries=config.max_retries,
            backoff_factor=config.backoff_factor,
            retry_on_status=config.retry_on_status,
            max_retry_after=config.max_retry_after,
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
        self._hero_stats_lock = asyncio.Lock()

        # Per-hero endpoints are cached per hero id, each behind its own lock: concurrent
        # calls for one hero collapse to a single request, while different heroes still
        # fetch in parallel instead of queueing behind one shared lock.
        self._hero_item_popularity_cache: dict[int, HeroItemPopularity] = {}
        self._hero_item_popularity_locks: dict[int, asyncio.Lock] = {}
        self._hero_matchups_cache: dict[int, HeroMatchups] = {}
        self._hero_matchups_locks: dict[int, asyncio.Lock] = {}
        self._hero_benchmarks_cache: dict[int, HeroBenchmarks] = {}
        self._hero_benchmarks_locks: dict[int, asyncio.Lock] = {}

        # Bumped by `clear_live_data()`. A fill remembers the value from before its fetch
        # and skips storing if it changed, so a request already in flight cannot put
        # pre-clear data back into a cache that was just emptied.
        self._live_generation = 0

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
                    "Hero id %s from /heroes not found in /constants/heroes; "
                    "using API data only",
                    hero_id,
                )
                merged_hero = dict(hero)

            hero_name = str(hero.get("name", ""))
            hero_ability_data = hero_abilities.get(hero_name)
            if hero_ability_data is None:
                logger.warning(
                    "Hero name %r not found in /constants/hero_abilities; "
                    "it will have no abilities or talents",
                    hero_name,
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
                    started = time.perf_counter()
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
                    logger.debug(
                        "Loaded %d heroes from 5 payloads in %.2fs; cached on client",
                        len(heroes),
                        time.perf_counter() - started,
                    )

        return list(self._heroes_cache)

    async def get_hero(
        self, hero_name: HeroName | str | None = None, *, hero_id: int | None = None
    ) -> Hero | None:
        """Look up a single hero by name or id.

        Populates the hero cache via `get_heroes()` if needed, then resolves from an index.
        `hero = await client.get_hero(HeroName.ANTI_MAGE)` is the usual form.

        Args:
            hero_name: The hero, as a `HeroName` member or its internal name string
                (`"npc_dota_hero_antimage"`). A plain string also covers heroes added in
                a patch newer than `HeroName`. May be passed positionally.
            hero_id: Numeric hero id. Keyword-only.

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
        that concurrent per-hero lookups collapse to one request. Call
        `clear_live_data()` to observe fresh numbers from the same client.

        Returns:
            A fresh list of statistics for all heroes. Mutating the list does not affect
            the cache.

        Raises:
            OpenDotaError: If the request fails or an entry cannot be normalized.
        """
        if self._hero_stats_cache is None:
            async with self._hero_stats_lock:
                if self._hero_stats_cache is None:
                    started = time.perf_counter()
                    generation = self._live_generation
                    raw_stats = await self._get("/heroStats")
                    stats = self._assembler.list_hero_stats(raw_stats)
                    if generation != self._live_generation:
                        logger.debug(
                            "Loaded statistics for %d heroes in %.2fs; not cached "
                            "because live data was cleared during the fetch",
                            len(stats),
                            time.perf_counter() - started,
                        )
                        return stats
                    self._hero_stats_by_id = {stat.hero_id: stat for stat in stats}
                    self._hero_stats_cache = stats
                    logger.debug(
                        "Loaded statistics for %d heroes in %.2fs; cached on client",
                        len(stats),
                        time.perf_counter() - started,
                    )

        return list(self._hero_stats_cache)

    async def _get_hero_stat(self, *, hero_id: int) -> HeroStats | None:
        """Look up one hero's live statistics; the fetch behind `Hero.get_stats()`.

        Private per AGENTS.md §3.6: callers reach it through `Hero.get_stats()`. Populates
        the stats cache via `get_hero_stats()` if needed, then resolves from an index, so
        gathering `get_stats()` over every hero still costs one request.

        Args:
            hero_id: Numeric hero id.

        Returns:
            The matching statistics, or `None` if `/heroStats` has no entry for the hero.

        Raises:
            OpenDotaError: If the underlying `get_hero_stats()` fetch fails.
        """
        stats = await self.get_hero_stats()
        if self._hero_stats_cache is None:
            # Cleared while the fetch was in flight, so it was not cached and the index
            # may be empty. Search what this call received instead.
            return next((stat for stat in stats if stat.hero_id == hero_id), None)
        return self._hero_stats_by_id.get(hero_id)

    async def _get_hero_item_popularity(self, *, hero_id: int) -> HeroItemPopularity:
        """Fetch a hero's item popularity; the fetch behind `Hero.get_item_popularity()`.

        Private per AGENTS.md §3.6: callers reach it through `Hero.get_item_popularity()`.
        Fetches `/heroes/{hero_id}/itemPopularity` alongside the item constants (via
        `get_items()`, so those are fetched at most once per client) and turns each item
        id into an `Item`. See `HeroItemPopularity` for what the counts measure.

        Cached per hero: concurrent calls for the same hero share one request, and calls
        for different heroes run in parallel.

        Args:
            hero_id: Numeric hero id.

        Returns:
            The hero's item popularity. OpenDota answers an unknown hero id with empty
            data rather than an error, so check `HeroItemPopularity.is_empty`.

        Raises:
            OpenDotaError: If a request fails or the payload is malformed.
        """
        cached = self._hero_item_popularity_cache.get(hero_id)
        if cached is not None:
            return cached

        # Get-or-create with no await in between, so racing tasks share one lock.
        lock = self._hero_item_popularity_locks.get(hero_id)
        if lock is None:
            lock = self._hero_item_popularity_locks[hero_id] = asyncio.Lock()

        async with lock:
            cached = self._hero_item_popularity_cache.get(hero_id)
            if cached is None:
                started = time.perf_counter()
                generation = self._live_generation
                raw, _ = await asyncio.gather(
                    self._get(f"/heroes/{hero_id}/itemPopularity"),
                    self.get_items(),
                )
                cached = self._assembler.normalize_hero_item_popularity(
                    raw, hero_id=hero_id, items_by_id=self._items_by_id
                )
                if generation != self._live_generation:
                    self._log_uncached("item popularity", hero_id)
                    return cached
                self._hero_item_popularity_cache[hero_id] = cached
                logger.debug(
                    "Loaded item popularity for hero %d (%d items across 4 phases) "
                    "in %.2fs; cached on client",
                    hero_id,
                    sum(
                        len(phase)
                        for phase in (
                            cached.start_game,
                            cached.early_game,
                            cached.mid_game,
                            cached.late_game,
                        )
                    ),
                    time.perf_counter() - started,
                )

        return cached

    async def _get_hero_matchups(self, *, hero_id: int) -> HeroMatchups:
        """Fetch a hero's matchups; the fetch behind `Hero.get_matchups()`.

        Private per AGENTS.md §3.6: callers reach it through `Hero.get_matchups()`.
        Fetches `/heroes/{hero_id}/matchups` alongside the hero constants (via
        `get_heroes()`, so those are fetched at most once per client) and turns each
        opposing hero id into a `Hero`. See `HeroMatchups` for what the counts measure.

        Cached per hero: concurrent calls for the same hero share one request, and calls
        for different heroes run in parallel.

        Args:
            hero_id: Numeric hero id.

        Returns:
            The hero's matchups. OpenDota answers an unknown hero id with an empty list
            rather than an error, so check `HeroMatchups.is_empty`.

        Raises:
            OpenDotaError: If a request fails or the payload is malformed.
        """
        cached = self._hero_matchups_cache.get(hero_id)
        if cached is not None:
            return cached

        # Get-or-create with no await in between, so racing tasks share one lock.
        lock = self._hero_matchups_locks.get(hero_id)
        if lock is None:
            lock = self._hero_matchups_locks[hero_id] = asyncio.Lock()

        async with lock:
            cached = self._hero_matchups_cache.get(hero_id)
            if cached is None:
                started = time.perf_counter()
                generation = self._live_generation
                raw, _ = await asyncio.gather(
                    self._get(f"/heroes/{hero_id}/matchups"),
                    self.get_heroes(),
                )
                cached = self._assembler.normalize_hero_matchups(
                    raw, hero_id=hero_id, heroes_by_id=self._heroes_by_id
                )
                if generation != self._live_generation:
                    self._log_uncached("matchups", hero_id)
                    return cached
                self._hero_matchups_cache[hero_id] = cached
                logger.debug(
                    "Loaded %d matchups for hero %d in %.2fs; cached on client",
                    len(cached.matchups),
                    hero_id,
                    time.perf_counter() - started,
                )

        return cached

    async def _get_hero_benchmarks(self, *, hero_id: int) -> HeroBenchmarks:
        """Fetch a hero's benchmarks; the fetch behind `Hero.get_benchmarks()`.

        Private per AGENTS.md §3.6: callers reach it through `Hero.get_benchmarks()`.
        Fetches `/benchmarks?hero_id={hero_id}` unfiltered; nothing else is joined. See
        `HeroBenchmarks` for what the values measure.

        Cached per hero: concurrent calls for the same hero share one request, and calls
        for different heroes run in parallel.

        Args:
            hero_id: Numeric hero id.

        Returns:
            The hero's benchmarks. OpenDota answers an unknown hero id with null values
            rather than an error, so check `HeroBenchmarks.is_empty`.

        Raises:
            OpenDotaError: If the request fails or the payload is malformed.
        """
        cached = self._hero_benchmarks_cache.get(hero_id)
        if cached is not None:
            return cached

        # Get-or-create with no await in between, so racing tasks share one lock.
        lock = self._hero_benchmarks_locks.get(hero_id)
        if lock is None:
            lock = self._hero_benchmarks_locks[hero_id] = asyncio.Lock()

        async with lock:
            cached = self._hero_benchmarks_cache.get(hero_id)
            if cached is None:
                started = time.perf_counter()
                generation = self._live_generation
                raw = await self._get("/benchmarks", params={"hero_id": hero_id})
                cached = self._assembler.normalize_hero_benchmarks(raw, hero_id=hero_id)
                if generation != self._live_generation:
                    self._log_uncached("benchmarks", hero_id)
                    return cached
                self._hero_benchmarks_cache[hero_id] = cached
                logger.debug(
                    "Loaded %d benchmark metrics for hero %d in %.2fs; cached on client",
                    len(cached.metrics),
                    hero_id,
                    time.perf_counter() - started,
                )

        return cached

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
                    started = time.perf_counter()
                    items_data = await self._get("/constants/items")
                    raw_items = [
                        {**data, "name": name} for name, data in items_data.items()
                    ]
                    items = self._assembler.list_items(raw_items)
                    self._items_by_id = {item.id: item for item in items}
                    self._items_by_name = {item.name: item for item in items}
                    self._items_cache = items
                    logger.debug(
                        "Loaded %d items in %.2fs; cached on client",
                        len(items),
                        time.perf_counter() - started,
                    )

        return list(self._items_cache)

    async def get_item(
        self, item_name: ItemName | str | None = None, *, item_id: int | None = None
    ) -> Item | None:
        """Look up a single item by name or id.

        Populates the item cache via `get_items()` if needed, then resolves from an index.
        `item = await client.get_item(ItemName.BLACK_KING_BAR)` is the usual form.

        Args:
            item_name: The item, as an `ItemName` member or its internal name string
                (`"blink"`). A plain string also covers items added in a patch newer than
                `ItemName`. May be passed positionally.
            item_id: Numeric item id. Keyword-only.

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

    @staticmethod
    def _log_uncached(what: str, hero_id: int) -> None:
        """Note that a fetch finished after `clear_live_data()` and was not cached."""
        logger.debug(
            "Loaded %s for hero %d but did not cache it: "
            "live data was cleared during the fetch",
            what,
            hero_id,
        )

    def clear_live_data(self) -> None:
        """Discard every cached live result so the next lookup fetches fresh numbers.

        Drops hero statistics, item popularity, matchups, and benchmarks. Nothing is
        fetched here: the next `Hero.get_stats()`, `Hero.get_item_popularity()`,
        `Hero.get_matchups()`, or `Hero.get_benchmarks()` call does that. The hero and item
        constants stay cached, since they only change with a patch. It is all-or-nothing;
        there is no per-hero form.

        A fetch already in flight when this is called still returns its data to the
        caller that started it, but does not repopulate the cache, so it cannot bring
        back numbers from before the call. Lookups made afterwards fetch again, and
        concurrent ones still share one request.
        """
        self._live_generation += 1
        self._hero_stats_cache = None
        self._hero_stats_by_id = {}
        self._hero_item_popularity_cache.clear()
        self._hero_matchups_cache.clear()
        self._hero_benchmarks_cache.clear()
        logger.debug(
            "Cleared cached live data (hero stats, item popularity, "
            "matchups, benchmarks)"
        )

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
