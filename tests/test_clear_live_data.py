"""Tests for `OpenDotaAsyncClient.clear_live_data()`."""

import asyncio
import logging

import pytest

from opendota_sdk.client import OpenDotaAsyncClient

_BENCHMARKS = {
    "hero_id": 1,
    "result": {"gold_per_min": [{"percentile": 0.5, "value": 400}]},
}


def _stat(hero_id: int, pub_pick: int = 1) -> dict:
    return {
        "id": hero_id,
        "name": f"npc_dota_hero_{hero_id}",
        "localized_name": f"H{hero_id}",
        "pub_pick": pub_pick,
        "pub_win": 0,
    }


def _client(handler) -> OpenDotaAsyncClient:
    client = OpenDotaAsyncClient()
    client._get = handler
    return client


@pytest.mark.asyncio
async def test_clear_forces_a_fresh_fetch_of_benchmarks():
    calls = []

    async def fake_get(path, **kwargs):
        calls.append(path)
        return _BENCHMARKS

    client = _client(fake_get)
    await client._get_hero_benchmarks(hero_id=1)
    await client._get_hero_benchmarks(hero_id=1)
    assert len(calls) == 1

    client.clear_live_data()
    await client._get_hero_benchmarks(hero_id=1)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_clear_empties_every_live_cache_and_keeps_constants():
    client = OpenDotaAsyncClient()
    client._heroes_cache = []
    client._items_cache = []
    client._hero_stats_cache = []
    vars(client)["_hero_item_popularity_cache"][1] = object()
    vars(client)["_hero_matchups_cache"][1] = object()
    vars(client)["_hero_benchmarks_cache"][1] = object()
    locks = (
        client._hero_item_popularity_locks.setdefault(1, asyncio.Lock()),
        client._hero_matchups_locks.setdefault(1, asyncio.Lock()),
        client._hero_benchmarks_locks.setdefault(1, asyncio.Lock()),
    )

    client.clear_live_data()

    assert client._hero_stats_cache is None
    assert not client._hero_item_popularity_cache
    assert not client._hero_matchups_cache
    assert not client._hero_benchmarks_cache
    assert client._heroes_cache == []
    assert client._items_cache == []
    assert client._hero_item_popularity_locks[1] is locks[0]
    assert client._hero_matchups_locks[1] is locks[1]
    assert client._hero_benchmarks_locks[1] is locks[2]


@pytest.mark.asyncio
async def test_gather_after_clear_still_collapses_to_one_request():
    calls = []

    async def fake_get(path, **kwargs):
        calls.append(path)
        await asyncio.sleep(0)
        return [_stat(i) for i in range(1, 6)]

    client = _client(fake_get)
    await client.get_hero_stats()
    client.clear_live_data()
    calls.clear()

    results = await asyncio.gather(
        *(client._get_hero_stat(hero_id=i) for i in range(1, 6))
    )

    assert calls == ["/heroStats"]
    assert [r.hero_id for r in results if r is not None] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_fetch_in_flight_during_clear_does_not_repopulate_the_cache():
    release = asyncio.Event()
    started = asyncio.Event()
    payloads = iter([[_stat(1, pub_pick=1)], [_stat(1, pub_pick=2)]])

    async def fake_get(path, **kwargs):
        payload = next(payloads)
        started.set()
        if payload[0]["pub_pick"] == 1:
            await release.wait()
        return payload

    client = _client(fake_get)
    stale = asyncio.create_task(client._get_hero_stat(hero_id=1))
    await started.wait()

    client.clear_live_data()
    release.set()
    stale_result = await stale

    # The caller that started the fetch still gets its answer ...
    assert stale_result is not None and stale_result.pub_picks == 1
    # ... but it was not cached, so the next lookup fetches fresh data.
    assert client._hero_stats_cache is None
    fresh = await client._get_hero_stat(hero_id=1)
    assert fresh is not None and fresh.pub_picks == 2


@pytest.mark.asyncio
async def test_per_hero_fetch_in_flight_during_clear_is_not_cached():
    release = asyncio.Event()
    started = asyncio.Event()
    calls = []

    async def fake_get(path, **kwargs):
        calls.append(path)
        started.set()
        if len(calls) == 1:
            await release.wait()
        return _BENCHMARKS

    client = _client(fake_get)
    task = asyncio.create_task(client._get_hero_benchmarks(hero_id=1))
    await started.wait()
    client.clear_live_data()
    release.set()
    await task

    assert not client._hero_benchmarks_cache
    await client._get_hero_benchmarks(hero_id=1)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_clear_logs_once_at_debug(caplog):
    client = OpenDotaAsyncClient()

    with caplog.at_level(logging.DEBUG, logger="opendota_sdk"):
        client.clear_live_data()

    records = [
        r for r in caplog.records if "Cleared cached live data" in r.getMessage()
    ]
    assert len(records) == 1
    assert records[0].levelno == logging.DEBUG
