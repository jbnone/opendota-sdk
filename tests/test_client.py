"""Tests for OpenDota client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._errors import OpenDotaError
from opendota_sdk.client import OpenDotaAsyncClient
from opendota_sdk.enums import (
    HeroAttackType,
    HeroPrimaryAttribute,
    HeroRole,
    HeroSkillBracket,
)
from opendota_sdk.models import AbilityBehavior, Hero, HeroStats, HeroTalent, Item


@pytest.mark.asyncio
@patch("opendota_sdk.client.AsyncHTTPTransport")
async def test_async_client_initialization(mock_transport_class):
    """Test async client initialization with config propagation."""
    mock_transport = MagicMock()
    mock_transport_class.return_value = mock_transport

    config = OpenDotaClientConfig(api_key="custom_key")
    client = OpenDotaAsyncClient(config=config)

    assert client._config.api_key == "custom_key"
    mock_transport_class.assert_called_once()


@pytest.mark.asyncio
async def test_get_heroes_returns_typed_hero_models():
    heroes_api = [
        {
            "id": 1,
            "name": "npc_dota_hero_antimage",
            "localized_name": "Anti-Mage",
            "primary_attr": "agi",
            "attack_type": "Melee",
            "roles": ["Carry", "Escape"],
            "legs": 2,
        }
    ]
    heroes_constants = {
        "1": {
            "img": "/apps/dota2/images/heroes/antimage_full.png",
            "icon": "/apps/dota2/images/heroes/icons/antimage.png",
            "base_health": 200,
            "base_health_regen": 1.0,
            "base_mana": 75,
            "base_mana_regen": 0.0,
            "base_armor": 0.0,
            "base_mr": 25,
            "base_attack_min": 29,
            "base_attack_max": 33,
            "base_attack_time": 100,
            "base_str": 21,
            "base_agi": 24,
            "base_int": 12,
            "str_gain": 1.6,
            "agi_gain": 2.8,
            "int_gain": 1.8,
            "attack_point": 0.3,
            "attack_range": 150,
            "projectile_speed": 0,
            "attack_rate": 1.4,
            "move_speed": 310,
            "turn_rate": 0.6,
            "cm_enabled": True,
            "day_vision": 1800,
            "night_vision": 800,
        }
    }

    hero_abilities = {
        "npc_dota_hero_antimage": {
            "abilities": ["antimage_mana_break", "generic_hidden"],
            "talents": [
                {"name": "special_bonus_hp_regen_3", "level": 1},
            ],
        }
    }
    abilities = {
        "antimage_mana_break": {
            "dname": "Mana Break",
            "behavior": "Passive",
            "dmg_type": "Physical",
            "desc": "Burns an opponent's mana on each attack.",
            "attrib": [
                {
                    "key": "percent_damage_per_burn",
                    "header": "MANA BURNED AS DAMAGE:",
                    "value": "60",
                },
                {
                    "key": "mana_per_hit",
                    "header": "MANA BURNED PER HIT:",
                    "value": ["25", "30"],
                },
            ],
        },
    }

    hero_lore = {"antimage": "The monks of Turstarkuri watched..."}

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(
            side_effect=[
                heroes_api,
                heroes_constants,
                hero_abilities,
                abilities,
                hero_lore,
            ]
        )

        heroes = await client.get_heroes()

    assert len(heroes) == 1
    hero = heroes[0]
    assert isinstance(hero, Hero)
    assert hero.localized_name == "Anti-Mage"
    assert hero.image == "/apps/dota2/images/heroes/antimage_full.png"
    assert hero.primary_attribute is HeroPrimaryAttribute.AGILITY
    assert hero.attack_type is HeroAttackType.MELEE
    assert hero.roles == [HeroRole.CARRY, HeroRole.ESCAPE]
    assert all(isinstance(role, HeroRole) for role in hero.roles)

    assert [ability.name for ability in hero.abilities] == [
        "antimage_mana_break",
        "generic_hidden",
    ]
    mana_break = hero.abilities[0]
    assert mana_break.title == "Mana Break"
    assert mana_break.behaviors == [AbilityBehavior.PASSIVE]
    assert mana_break.attributes[1].value == ["25", "30"]
    assert mana_break.attributes[1].display == "MANA BURNED PER HIT:"
    generic_hidden = hero.abilities[1]
    assert generic_hidden.title == "Generic Hidden"
    assert hero.lore == "The monks of Turstarkuri watched..."
    assert hero.talents == [
        HeroTalent(
            name="special_bonus_hp_regen_3",
            level=1,
            title="Special Bonus Hp Regen 3",
        )
    ]


@pytest.mark.asyncio
async def test_get_heroes_caches_after_first_call():
    heroes_api = [
        {
            "id": 1,
            "name": "npc_dota_hero_antimage",
            "localized_name": "Anti-Mage",
            "primary_attr": "agi",
            "attack_type": "Melee",
            "roles": ["Carry"],
            "legs": 2,
        }
    ]
    heroes_constants = {"1": {}}

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=[heroes_api, heroes_constants, {}, {}, {}])

        first = await client.get_heroes()
        second = await client.get_heroes()

    assert first == second
    assert first[0] is second[0]
    assert client._get.await_count == 5


@pytest.mark.asyncio
async def test_get_heroes_raises_opendota_error_on_malformed_hero():
    heroes_api = [{"id": 1, "name": "npc_dota_hero_antimage"}]
    heroes_constants: dict[str, dict] = {}

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=[heroes_api, heroes_constants, {}, {}, {}])

        with pytest.raises(OpenDotaError, match="localized_name"):
            await client.get_heroes()


_ANTIMAGE_HEROES_API = [
    {
        "id": 1,
        "name": "npc_dota_hero_antimage",
        "localized_name": "Anti-Mage",
        "primary_attr": "agi",
        "attack_type": "Melee",
        "roles": ["Carry"],
    }
]
_ANTIMAGE_HEROES_CONSTANTS = {"1": {}}


def _antimage_side_effect() -> list:
    return [_ANTIMAGE_HEROES_API, _ANTIMAGE_HEROES_CONSTANTS, {}, {}, {}]


@pytest.mark.asyncio
async def test_get_hero_by_id_returns_matching_hero():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_antimage_side_effect())

        hero = await client.get_hero(hero_id=1)

    assert isinstance(hero, Hero)
    assert hero.localized_name == "Anti-Mage"


@pytest.mark.asyncio
async def test_get_hero_by_name_returns_matching_hero():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_antimage_side_effect())

        hero = await client.get_hero(hero_name="npc_dota_hero_antimage")

    assert isinstance(hero, Hero)
    assert hero.id == 1


@pytest.mark.asyncio
async def test_get_hero_not_found_returns_none():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_antimage_side_effect())

        hero = await client.get_hero(hero_id=999)

    assert hero is None


@pytest.mark.asyncio
async def test_get_hero_reuses_heroes_cache():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_antimage_side_effect())

        await client.get_hero(hero_id=1)
        await client.get_hero(hero_name="npc_dota_hero_antimage")

    assert client._get.await_count == 5


@pytest.mark.asyncio
async def test_get_hero_requires_exactly_one_lookup_key():
    async with OpenDotaAsyncClient() as client:
        with pytest.raises(ValueError, match="Either hero_id or hero_name"):
            await client.get_hero()

        with pytest.raises(ValueError, match="Provide either hero_id or hero_name"):
            await client.get_hero(hero_id=1, hero_name="npc_dota_hero_antimage")


_BLINK_ITEMS_DATA = {"blink": {"id": 1, "dname": "Blink Dagger", "cost": 2250}}


@pytest.mark.asyncio
async def test_get_items_returns_typed_item_models():
    items_data = {
        "blink": {"id": 1, "dname": "Blink Dagger", "cost": 2250},
        "recipe_arcane_blink": {
            "id": 606,
            "dname": "Arcane Blink Recipe",
            "cost": 1750,
            "behavior": False,
        },
    }

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=items_data)

        items = await client.get_items()

    assert len(items) == 2
    assert all(isinstance(item, Item) for item in items)
    assert {item.name for item in items} == {"blink", "recipe_arcane_blink"}


@pytest.mark.asyncio
async def test_get_item_by_id_returns_typed_item_model():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_BLINK_ITEMS_DATA)

        item = await client.get_item(item_id=1)

    assert isinstance(item, Item)
    assert item.name == "blink"
    assert item.descriptive_name == "Blink Dagger"


@pytest.mark.asyncio
async def test_get_item_by_name_returns_typed_item_model():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_BLINK_ITEMS_DATA)

        item = await client.get_item(item_name="blink")

    assert isinstance(item, Item)
    assert item.name == "blink"


@pytest.mark.asyncio
async def test_get_item_not_found_returns_none():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_BLINK_ITEMS_DATA)

        item = await client.get_item(item_id=999)

    assert item is None


@pytest.mark.asyncio
async def test_get_item_requires_exactly_one_lookup_key():
    async with OpenDotaAsyncClient() as client:
        with pytest.raises(ValueError, match="Either item_id or item_name"):
            await client.get_item()

        with pytest.raises(ValueError, match="Provide either item_id or item_name"):
            await client.get_item(item_id=1, item_name="blink")


@pytest.mark.asyncio
async def test_get_item_shares_cache_and_identity_with_get_items():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_BLINK_ITEMS_DATA)

        items = await client.get_items()
        item = await client.get_item(item_id=1)

        client._get.assert_awaited_once()

    assert item is items[0]


@pytest.mark.asyncio
async def test_get_items_calls_transport_exactly_once():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value={})

        await client.get_items()

        client._get.assert_awaited_once_with("/constants/items")


@pytest.mark.asyncio
async def test_get_items_caches_after_first_call():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_BLINK_ITEMS_DATA)

        first = await client.get_items()
        second = await client.get_items()

    assert first == second
    client._get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_items_returned_list_mutation_does_not_affect_cache():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_BLINK_ITEMS_DATA)

        first = await client.get_items()
        first.append(first[0])
        second = await client.get_items()

    assert len(second) == 1


@pytest.mark.asyncio
async def test_get_heroes_returned_list_mutation_does_not_affect_cache():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_antimage_side_effect())

        first = await client.get_heroes()
        first.append(first[0])
        second = await client.get_heroes()

    assert len(second) == 1


@pytest.mark.asyncio
async def test_get_items_concurrent_calls_fetch_only_once():
    async def slow_get(path, **kwargs):
        await asyncio.sleep(0)
        return _BLINK_ITEMS_DATA

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=slow_get)

        results = await asyncio.gather(client.get_items(), client.get_items())

    client._get.assert_awaited_once()
    assert results[0] == results[1]


@pytest.mark.asyncio
async def test_get_heroes_concurrent_calls_fetch_only_once():
    async def slow_get(path, **kwargs):
        await asyncio.sleep(0)
        responses = {
            "/heroes": _ANTIMAGE_HEROES_API,
            "/constants/heroes": _ANTIMAGE_HEROES_CONSTANTS,
        }
        return responses.get(path, {})

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=slow_get)

        results = await asyncio.gather(client.get_heroes(), client.get_heroes())

    assert client._get.await_count == 5
    assert results[0] == results[1]


@pytest.mark.asyncio
async def test_get_items_end_to_end_with_real_transport_and_assembler():
    raw_items_payload = {
        "blink": {"id": 1, "dname": "Blink Dagger", "cost": 2250},
        "recipe_arcane_blink": {
            "id": 606,
            "dname": "Arcane Blink Recipe",
            "cost": 1750,
            "behavior": False,
        },
    }

    async with OpenDotaAsyncClient() as client:
        client._transport.request_json = AsyncMock(return_value=raw_items_payload)

        items = await client.get_items()

    assert len(items) == 2
    assert {item.name for item in items} == {"blink", "recipe_arcane_blink"}


@pytest.mark.asyncio
async def test_get_items_handles_real_items_json_payload(real_items_json):
    async with OpenDotaAsyncClient() as client:
        client._transport.request_json = AsyncMock(return_value=real_items_json)

        items = await client.get_items()

    assert len(items) == len(real_items_json)
    assert all(isinstance(item, Item) for item in items)


_HERO_STATS_API = [
    {
        "id": 1,
        "name": "npc_dota_hero_antimage",
        "1_pick": 16301,
        "1_win": 8008,
        "pub_pick": 521236,
        "pub_win": 259663,
        "pro_pick": 2,
        "pro_win": 1,
        "pro_ban": 1,
    },
    {
        "id": 2,
        "name": "npc_dota_hero_axe",
        "1_pick": 20863,
        "1_win": 10969,
        "pub_pick": 857075,
        "pub_win": 432005,
    },
]


@pytest.mark.asyncio
async def test_get_hero_stats_returns_typed_models():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_HERO_STATS_API)

        stats = await client.get_hero_stats()

    assert len(stats) == 2
    assert all(isinstance(entry, HeroStats) for entry in stats)
    assert [entry.hero_name for entry in stats] == [
        "npc_dota_hero_antimage",
        "npc_dota_hero_axe",
    ]
    antimage = stats[0]
    assert antimage.pub_picks == 521236
    assert antimage.brackets[0].bracket is HeroSkillBracket.HERALD
    client._get.assert_awaited_once_with("/heroStats")


@pytest.mark.asyncio
async def test_get_hero_stats_caches_and_returns_fresh_lists():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_HERO_STATS_API)

        first = await client.get_hero_stats()
        second = await client.get_hero_stats()

    assert client._get.await_count == 1
    assert first == second
    assert first is not second

    first.clear()
    assert len(second) == 2


@pytest.mark.asyncio
async def test_get_hero_stats_concurrent_calls_fetch_once():
    async def slow_get(path, **kwargs):
        await asyncio.sleep(0.01)
        return _HERO_STATS_API

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=slow_get)

        results = await asyncio.gather(client.get_hero_stats(), client.get_hero_stats())

    assert client._get.await_count == 1
    assert results[0] == results[1]


@pytest.mark.asyncio
async def test_get_hero_stat_by_id_and_name():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_HERO_STATS_API)

        by_id = await client.get_hero_stat(hero_id=2)
        by_name = await client.get_hero_stat(hero_name="npc_dota_hero_axe")
        missing = await client.get_hero_stat(hero_id=999)

    assert by_id is not None
    assert by_id.hero_name == "npc_dota_hero_axe"
    assert by_name == by_id
    assert missing is None


@pytest.mark.asyncio
async def test_get_hero_stat_requires_exactly_one_identifier():
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=_HERO_STATS_API)

        with pytest.raises(ValueError, match="Either hero_id or hero_name"):
            await client.get_hero_stat()

        with pytest.raises(ValueError, match="not both"):
            await client.get_hero_stat(hero_id=1, hero_name="npc_dota_hero_antimage")
