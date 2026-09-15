"""Tests for the ambient client binding behind model relationship methods."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from opendota_sdk._context import active_client
from opendota_sdk._errors import OpenDotaError
from opendota_sdk.client import OpenDotaAsyncClient
from opendota_sdk.enums import HeroAttackType, HeroPrimaryAttribute
from opendota_sdk.models import Hero, HeroStats


def _hero(hero_id: int = 1) -> Hero:
    return Hero(
        id=hero_id,
        name="npc_dota_hero_antimage",
        localized_name="Anti-Mage",
        primary_attribute=HeroPrimaryAttribute.AGILITY,
        attack_type=HeroAttackType.MELEE,
        roles=[],
        legs=2,
        image="",
        icon="",
        base_health=120,
        base_health_regen=1.0,
        base_mana=75,
        base_mana_regen=0.0,
        base_armor=2.0,
        base_magic_resistance=25,
        base_attack_min=29,
        base_attack_max=33,
        base_attack_time=100,
        base_strength=21,
        base_agility=24,
        base_intelligence=12,
        strength_gain=1.6,
        agility_gain=2.8,
        intelligence_gain=1.8,
        attack_point=0.3,
        attack_range=150,
        projectile_speed=0,
        attack_rate=1.4,
        move_speed=310,
        turn_rate=None,
        captains_mode_enabled=True,
        day_vision=1800,
        night_vision=800,
    )


def test_active_client_without_binding_raises_with_guidance():
    with pytest.raises(OpenDotaError, match="No active OpenDotaAsyncClient"):
        active_client()


@pytest.mark.asyncio
async def test_hero_get_stats_outside_client_scope_raises():
    hero = _hero()

    with pytest.raises(OpenDotaError, match="No active OpenDotaAsyncClient"):
        await hero.get_stats()


@pytest.mark.asyncio
async def test_hero_get_stats_delegates_to_active_client():
    hero = _hero(hero_id=5)

    async with OpenDotaAsyncClient() as client:
        client.get_hero_stat = AsyncMock(return_value="sentinel")

        result = await hero.get_stats()

    assert result == "sentinel"
    client.get_hero_stat.assert_awaited_once_with(hero_id=5)


@pytest.mark.asyncio
async def test_context_manager_binds_and_unbinds():
    async with OpenDotaAsyncClient() as client:
        assert active_client() is client

    with pytest.raises(OpenDotaError):
        active_client()


@pytest.mark.asyncio
async def test_nested_clients_restore_the_outer_binding():
    async with OpenDotaAsyncClient() as outer:
        async with OpenDotaAsyncClient() as inner:
            assert active_client() is inner
        assert active_client() is outer


@pytest.mark.asyncio
async def test_activate_and_deactivate_outside_context_manager():
    client = OpenDotaAsyncClient()
    client.activate()
    try:
        assert active_client() is client
    finally:
        client.deactivate()
        await client.close()

    with pytest.raises(OpenDotaError):
        active_client()


def test_deactivate_without_binding_is_a_no_op():
    OpenDotaAsyncClient().deactivate()

    with pytest.raises(OpenDotaError):
        active_client()


@pytest.mark.asyncio
async def test_concurrent_hero_relationships_share_a_single_fetch():
    """The client's cache+lock makes gather() over many heroes collapse to one request."""
    payload = [
        {"id": hero_id, "name": f"npc_dota_hero_{hero_id}", "pub_pick": hero_id}
        for hero_id in range(1, 21)
    ]

    async def slow_get(path, **kwargs):
        await asyncio.sleep(0.01)
        return payload

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=slow_get)
        heroes = [_hero(hero_id) for hero_id in range(1, 21)]

        results = await asyncio.gather(*(hero.get_stats() for hero in heroes))

    assert client._get.await_count == 1
    assert all(isinstance(result, HeroStats) for result in results)
    assert [result.hero_id for result in results if result is not None] == list(
        range(1, 21)
    )
