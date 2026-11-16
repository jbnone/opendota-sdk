"""Pins the `get_hero()` / `get_item()` overloads; `ty check` verifies the `assert_type`s."""

from typing import assert_type

from opendota_sdk import HeroName, ItemName, OpenDotaAsyncClient
from opendota_sdk.models import Hero, Item


async def _typing_only(client: OpenDotaAsyncClient) -> None:
    assert_type(await client.get_hero(HeroName.ANTI_MAGE), Hero)
    assert_type(await client.get_hero("npc_dota_hero_antimage"), Hero | None)
    assert_type(await client.get_hero(hero_id=1), Hero | None)
    assert_type(await client.get_item(ItemName.BLINK_DAGGER), Item)
    assert_type(await client.get_item("blink"), Item | None)
    assert_type(await client.get_item(item_id=1), Item | None)


def test_overloads_keep_runtime_names() -> None:
    """The overloads do not replace the real coroutine functions."""
    assert OpenDotaAsyncClient.get_hero.__name__ == "get_hero"
    assert OpenDotaAsyncClient.get_item.__name__ == "get_item"
