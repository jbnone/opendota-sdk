from typing import Any

from opendota_sdk.http._transport import AsyncHTTPTransport


class ConstantsRegistry:
    def __init__(self, transport: AsyncHTTPTransport) -> None:
        self._transport = transport
        self._heroes: dict[str, Any] | None = None
        self._items: dict[str, Any] | None = None

    async def _load(self, path: str) -> dict[str, Any]:
        return await self._transport.request_json(method="GET", path=path)

    async def heroes(self) -> dict[str, Any]:
        if self._heroes is None:
            self._heroes = await self._load("/constants/heroes")
        return self._heroes

    async def items(self) -> dict[str, Any]:
        if self._items is None:
            self._items = await self._load("/constants/items")
        return self._items

    async def get_hero(self, hero_id: int) -> dict[str, Any] | None:
        heroes = await self.heroes()
        return heroes.get(str(hero_id))

    async def get_item(self, item_id: int) -> dict[str, Any] | None:
        items = await self.items()
        return items.get(str(item_id))
