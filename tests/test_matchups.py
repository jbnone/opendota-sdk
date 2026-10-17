"""Tests for hero matchups: assembly, per-hero client caching, relationship method, logs."""

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from opendota_sdk import OpenDotaAsyncClient, OpenDotaError
from opendota_sdk.assembler import Assembler
from opendota_sdk.models import Hero

_HERO_NAMES = {1: "Anti-Mage", 2: "Axe", 3: "Bane", 4: "Bloodseeker"}


def _hero(hero_id: int) -> Hero:
    return Assembler().normalize_hero(
        {
            "id": hero_id,
            "name": f"npc_dota_hero_{hero_id}",
            "localized_name": _HERO_NAMES[hero_id],
            "primary_attr": "agi",
            "attack_type": "Melee",
            "roles": ["Carry"],
        }
    )


@pytest.fixture
def heroes_by_id():
    return {hero_id: _hero(hero_id) for hero_id in _HERO_NAMES}


@pytest.fixture
def assembler():
    return Assembler()


# --- Assembler -------------------------------------------------------------------


def test_matchups_resolve_ids_to_heroes(assembler, heroes_by_id):
    result = assembler.normalize_hero_matchups(
        [{"hero_id": 2, "games_played": 91, "wins": 45}],
        hero_id=1,
        heroes_by_id=heroes_by_id,
    )

    assert result.hero_id == 1
    assert not result.is_empty
    assert result.matchups[0].hero.localized_name == "Axe"
    assert result.matchups[0].games_played == 91
    assert result.matchups[0].wins == 45


def test_matchups_sort_most_games_first_with_stable_ties(assembler, heroes_by_id):
    result = assembler.normalize_hero_matchups(
        [
            {"hero_id": 4, "games_played": 10, "wins": 5},
            {"hero_id": 3, "games_played": 50, "wins": 5},
            {"hero_id": 2, "games_played": 10, "wins": 5},
            {"hero_id": 1, "games_played": 80, "wins": 5},
        ],
        hero_id=9,
        heroes_by_id=heroes_by_id,
    )

    assert [m.hero.localized_name for m in result.matchups] == [
        "Anti-Mage",
        "Bane",
        "Axe",
        "Bloodseeker",
    ]


def test_matchup_win_rate_is_none_without_games(assembler, heroes_by_id):
    result = assembler.normalize_hero_matchups(
        [
            {"hero_id": 2, "games_played": 0, "wins": 0},
            {"hero_id": 3, "games_played": 4, "wins": 1},
        ],
        hero_id=1,
        heroes_by_id=heroes_by_id,
    )

    by_name = {m.hero.localized_name: m for m in result.matchups}
    assert by_name["Axe"].win_rate is None
    assert by_name["Bane"].win_rate == 0.25


def test_matchups_for_unknown_hero_is_empty(assembler, heroes_by_id):
    """OpenDota answers an unknown hero id with `[]` and HTTP 200."""
    result = assembler.normalize_hero_matchups(
        [], hero_id=99999, heroes_by_id=heroes_by_id
    )

    assert result.is_empty


def test_matchups_drop_unknown_heroes_with_one_warning(assembler, heroes_by_id, caplog):
    raw = [
        {"hero_id": 2, "games_played": 5, "wins": 1},
        {"hero_id": 9002, "games_played": 3, "wins": 1},
        {"hero_id": 9001, "games_played": 2, "wins": 1},
    ]

    with caplog.at_level(logging.WARNING, logger="opendota_sdk"):
        result = assembler.normalize_hero_matchups(
            raw, hero_id=1, heroes_by_id=heroes_by_id
        )

    assert [m.hero.id for m in result.matchups] == [2]
    assert result.raw == raw, "dropped ids stay available on raw"
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (
            logging.WARNING,
            (
                "Matchups for hero 1 reference 2 hero id(s) missing from the hero "
                "constants (9001, 9002); leaving them out"
            ),
        )
    ]


def test_matchups_log_nothing_when_everything_resolves(assembler, heroes_by_id, caplog):
    with caplog.at_level(logging.DEBUG, logger="opendota_sdk"):
        assembler.normalize_hero_matchups(
            [{"hero_id": 2, "games_played": 5, "wins": 1}],
            hero_id=1,
            heroes_by_id=heroes_by_id,
        )

    assert caplog.records == []


@pytest.mark.parametrize(
    "raw",
    [
        {},
        "nope",
        None,
        ["nope"],
        [{"games_played": 5, "wins": 1}],
        [{"hero_id": 2, "wins": 1}],
        [{"hero_id": 2, "games_played": 5, "wins": "many"}],
    ],
)
def test_matchups_reject_malformed_payloads(assembler, heroes_by_id, raw):
    with pytest.raises(OpenDotaError, match="Cannot build HeroMatchups"):
        assembler.normalize_hero_matchups(raw, hero_id=1, heroes_by_id=heroes_by_id)


# --- Client ----------------------------------------------------------------------


def _matchups_get(calls=None, delay=0.0, inflight=None, payload=None):
    """Path-keyed `_get` stand-in; optionally records calls and peak concurrency."""

    async def fake_get(path, **kwargs):
        if calls is not None:
            calls.append(path)
        if inflight is not None:
            inflight["now"] += 1
            inflight["peak"] = max(inflight["peak"], inflight["now"])
        try:
            await asyncio.sleep(delay)
        finally:
            if inflight is not None:
                inflight["now"] -= 1
        if not path.endswith("/matchups"):
            raise AssertionError(f"unexpected path {path}")
        if payload is not None:
            return payload
        return [{"hero_id": 2, "games_played": 91, "wins": 45}]

    return fake_get


def _stub_heroes(client, heroes_by_id):
    client.get_heroes = AsyncMock(return_value=list(heroes_by_id.values()))
    client._heroes_by_id = heroes_by_id


@pytest.mark.asyncio
async def test_get_hero_matchups_resolves_heroes(heroes_by_id):
    async with OpenDotaAsyncClient() as client:
        _stub_heroes(client, heroes_by_id)
        client._get = AsyncMock(side_effect=_matchups_get())

        result = await client._get_hero_matchups(hero_id=1)

    assert result.hero_id == 1
    assert result.matchups[0].hero.localized_name == "Axe"
    assert result.matchups[0].games_played == 91
    assert result.matchups[0].wins == 45


@pytest.mark.asyncio
async def test_get_hero_matchups_is_cached_per_hero(heroes_by_id):
    calls = []
    async with OpenDotaAsyncClient() as client:
        _stub_heroes(client, heroes_by_id)
        client._get = AsyncMock(side_effect=_matchups_get(calls))

        first = await client._get_hero_matchups(hero_id=1)
        second = await client._get_hero_matchups(hero_id=1)
        await client._get_hero_matchups(hero_id=2)

    assert first is second
    assert sorted(calls) == ["/heroes/1/matchups", "/heroes/2/matchups"]


@pytest.mark.asyncio
async def test_concurrent_matchups_calls_for_one_hero_share_one_request(heroes_by_id):
    calls = []
    async with OpenDotaAsyncClient() as client:
        _stub_heroes(client, heroes_by_id)
        client._get = AsyncMock(side_effect=_matchups_get(calls, delay=0.01))

        results = await asyncio.gather(
            *(client._get_hero_matchups(hero_id=1) for _ in range(5))
        )

    assert calls.count("/heroes/1/matchups") == 1
    assert all(result is results[0] for result in results)


@pytest.mark.asyncio
async def test_different_heroes_fetch_matchups_in_parallel_not_in_series(heroes_by_id):
    """Per-hero locks: one shared lock would serialize these and peak at 1 in flight."""
    calls = []
    inflight = {"now": 0, "peak": 0}
    async with OpenDotaAsyncClient() as client:
        _stub_heroes(client, heroes_by_id)
        client._get = AsyncMock(side_effect=_matchups_get(calls, 0.01, inflight))

        await asyncio.gather(
            *(client._get_hero_matchups(hero_id=hero_id) for hero_id in range(1, 6))
        )

    assert len(calls) == 5
    assert inflight["peak"] == 5


@pytest.mark.asyncio
async def test_unknown_hero_matchups_is_empty_not_an_error(heroes_by_id):
    async with OpenDotaAsyncClient() as client:
        _stub_heroes(client, heroes_by_id)
        client._get = AsyncMock(side_effect=_matchups_get(payload=[]))

        result = await client._get_hero_matchups(hero_id=99999)

    assert result.is_empty


@pytest.mark.asyncio
async def test_matchups_log_their_cache_fill_once(heroes_by_id, caplog):
    caplog.set_level(logging.DEBUG, logger="opendota_sdk")

    async with OpenDotaAsyncClient() as client:
        _stub_heroes(client, heroes_by_id)
        client._get = AsyncMock(side_effect=_matchups_get())
        await client._get_hero_matchups(hero_id=1)
        await client._get_hero_matchups(hero_id=1)

    fills = [
        (r.levelno, r.getMessage())
        for r in caplog.records
        if "matchups" in r.getMessage()
    ]
    assert len(fills) == 1
    level, message = fills[0]
    assert level == logging.DEBUG
    assert message.startswith("Loaded 1 matchups for hero 1 in ")


# --- Relationship method ---------------------------------------------------------


@pytest.mark.asyncio
async def test_hero_get_matchups_outside_client_scope_raises():
    with pytest.raises(OpenDotaError, match="No active OpenDotaAsyncClient"):
        await _hero(1).get_matchups()


@pytest.mark.asyncio
async def test_hero_get_matchups_delegates_to_active_client():
    """A one-line delegation: the client still owns the fetch, cache, and assembly."""
    async with OpenDotaAsyncClient() as client:
        client._get_hero_matchups = AsyncMock(return_value="sentinel")

        result = await _hero(3).get_matchups()

    assert result == "sentinel"
    client._get_hero_matchups.assert_awaited_once_with(hero_id=3)
