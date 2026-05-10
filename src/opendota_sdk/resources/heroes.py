from typing import Any

from opendota_sdk.models import Hero, Item
from opendota_sdk.resources._base import AsyncResourceBase


class HeroesAsyncResource(AsyncResourceBase):
    async def list(self) -> list[Hero]:
        heroes_api: list[dict[str, Any]] = await self._get("/heroes")
        heroes = []
        for hero in heroes_api:
            constants = await self._constants.get_hero(hero["id"])
            heroes.append(Hero.from_api(hero, constants, loader=self))
        return heroes

    async def get(self, hero_id: int | str) -> Hero:
        if isinstance(hero_id, str):
            return await self.by_name(hero_id)
        for hero in await self.list():
            if hero.id == hero_id:
                return hero
        raise ValueError(f"Hero with id {hero_id} not found")

    async def by_name(self, name: str) -> Hero:
        lowered = name.lower()
        for hero in await self.list():
            if hero.name.lower() == lowered or hero.localized_name.lower() == lowered:
                return hero
        raise ValueError(f"Hero named {name!r} not found")

    async def popular_items(self, hero_id: int) -> list[Item]:
        raw_items: list[dict[str, Any]] = await self._get(f"/heroes/{hero_id}/items")
        return [Item.from_api(item) for item in raw_items]
