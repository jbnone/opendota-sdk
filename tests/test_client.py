"""Tests for OpenDota client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from opendota_sdk.client import OpenDotaAsyncClient
from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk.enums import HeroAttackType, HeroPrimaryAttr, HeroRole
from opendota_sdk.models import Hero, Item


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
@patch("opendota_sdk.client.AsyncHTTPTransport")
async def test_async_client_context_manager(mock_transport_class):
    """Test async client as context manager."""
    mock_transport = MagicMock()
    mock_transport_class.return_value = mock_transport

    async def async_close():
        pass

    mock_transport.close = async_close

    async with OpenDotaAsyncClient() as client:
        assert client is not None


@pytest.mark.asyncio
@patch("opendota_sdk.client.AsyncHTTPTransport")
async def test_async_close(mock_transport_class):
    """Test async client close method."""
    mock_transport = MagicMock()
    mock_transport_class.return_value = mock_transport

    async def async_close():
        pass

    mock_transport.close = async_close

    client = OpenDotaAsyncClient()
    await client.close()


@pytest.mark.asyncio
async def test_get_heroes_returns_typed_hero_models():
    heroes_api = [
        {
            "id": 1,
            "name": "npc_dota_hero_antimage",
            "localized_name": "Anti-Mage",
            "primary_attr": HeroPrimaryAttr.AGI,
            "attack_type": HeroAttackType.MELEE,
            "roles": [HeroRole.CARRY],
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

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=[heroes_api, heroes_constants])

        heroes = await client.get_heroes()

    assert len(heroes) == 1
    assert isinstance(heroes[0], Hero)
    assert heroes[0].localized_name == "Anti-Mage"
    assert heroes[0].img == "/apps/dota2/images/heroes/antimage_full.png"


@pytest.mark.asyncio
async def test_get_items_returns_typed_item_models():
    raw_items = [
        {"id": 1, "name": "blink", "dname": "Blink Dagger", "cost": 2250},
        {
            "id": 606,
            "name": "recipe_arcane_blink",
            "dname": "Arcane Blink Recipe",
            "cost": 1750,
            "behavior": False,
        },
    ]

    async with OpenDotaAsyncClient() as client:
        client._constants.get_items = AsyncMock(return_value=raw_items)

        items = await client.get_items()

    assert len(items) == 2
    assert all(isinstance(item, Item) for item in items)
    assert items[0].name == "blink"
    assert items[0].descriptive_name == "Blink Dagger"


@pytest.mark.asyncio
async def test_get_items_calls_constants_registry_exactly_once():
    async with OpenDotaAsyncClient() as client:
        client._constants.get_items = AsyncMock(return_value=[])

        await client.get_items()

        client._constants.get_items.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_items_end_to_end_with_real_constants_registry_and_assembler():
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
