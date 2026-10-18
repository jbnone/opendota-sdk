"""Tests for hero benchmarks: assembly, per-hero client caching, relationship method, logs.

Also the regression sweep over recorded real `/benchmarks` payloads, and the check that
`BenchmarkMetric` still has a member for every metric OpenDota reports.
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock

import pytest

from opendota_sdk import (
    BenchmarkMetric,
    HeroBenchmarks,
    OpenDotaAsyncClient,
    OpenDotaError,
)
from opendota_sdk.assembler import Assembler
from opendota_sdk.models import Hero

from .conftest import FIXTURES_DIR

API_FIXTURES = FIXTURES_DIR / "opendota_api"


def _hero(hero_id: int) -> Hero:
    return Assembler().normalize_hero(
        {
            "id": hero_id,
            "name": f"npc_dota_hero_{hero_id}",
            "localized_name": f"Hero {hero_id}",
            "primary_attr": "agi",
            "attack_type": "Melee",
            "roles": ["Carry"],
        }
    )


def _payload(hero_id=1, value=500, extra=None):
    result = {
        "gold_per_min": [
            {"percentile": 0.9, "value": value + 100},
            {"percentile": 0.5, "value": value},
            {"percentile": 0.95, "value": value + 150},
        ]
    }
    result.update(extra or {})
    return {"hero_id": hero_id, "result": result}


@pytest.fixture
def assembler():
    return Assembler()


# --- Assembler -------------------------------------------------------------------


def test_benchmarks_fold_into_typed_sorted_points(assembler):
    result = assembler.normalize_hero_benchmarks(_payload(), hero_id=1)

    gpm = result.get(BenchmarkMetric.GOLD_PER_MINUTE)
    assert gpm is not None
    assert gpm.metric is BenchmarkMetric.GOLD_PER_MINUTE
    assert [p.percentile for p in gpm.points] == [0.5, 0.9, 0.95]
    assert gpm.value_at(0.5) == 500
    assert gpm.value_at(0.95) == 650
    assert not result.is_empty


def test_get_accepts_the_enum_or_its_plain_key(assembler):
    result = assembler.normalize_hero_benchmarks(_payload(), hero_id=1)

    assert result.get("gold_per_min") is result.get(BenchmarkMetric.GOLD_PER_MINUTE)
    assert result.get(BenchmarkMetric.TOWER_DAMAGE) is None


def test_value_at_is_none_for_unreported_percentiles(assembler):
    gpm = assembler.normalize_hero_benchmarks(_payload(), hero_id=1).get("gold_per_min")

    assert gpm is not None
    assert gpm.value_at(0.42) is None


def test_null_values_become_none_not_zero(assembler):
    raw = {
        "hero_id": 99999,
        "result": {"gold_per_min": [{"percentile": 0.5, "value": None}]},
    }

    result = assembler.normalize_hero_benchmarks(raw, hero_id=99999)

    gpm = result.get(BenchmarkMetric.GOLD_PER_MINUTE)
    assert gpm is not None
    assert gpm.value_at(0.5) is None
    assert gpm.points[0].value is None
    assert result.is_empty


def test_unknown_metric_is_kept_under_its_plain_key_with_one_debug_line(
    assembler, caplog
):
    extra = {"new_stat": [{"percentile": 0.5, "value": 3}]}

    with caplog.at_level(logging.DEBUG, logger="opendota_sdk"):
        result = assembler.normalize_hero_benchmarks(_payload(extra=extra), hero_id=1)

    novel = result.get("new_stat")
    assert novel is not None
    assert novel.metric == "new_stat"
    assert not isinstance(novel.metric, BenchmarkMetric)
    lines = [(r.levelno, r.getMessage()) for r in caplog.records]
    assert lines == [
        (
            logging.DEBUG,
            (
                "Benchmarks for hero 1 include 1 metric(s) with no BenchmarkMetric "
                "member (new_stat); keeping them under their plain keys"
            ),
        )
    ]


def test_known_metrics_log_nothing(assembler, caplog):
    with caplog.at_level(logging.DEBUG, logger="opendota_sdk"):
        assembler.normalize_hero_benchmarks(_payload(), hero_id=1)

    assert caplog.records == []


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {"hero_id": 1},
        {"hero_id": 1, "result": []},
        {"hero_id": 1, "result": {"gold_per_min": {}}},
        {"hero_id": 1, "result": {"gold_per_min": ["x"]}},
        {"hero_id": 1, "result": {"gold_per_min": [{"value": 1}]}},
        {"hero_id": 1, "result": {"gold_per_min": [{"percentile": 0.5, "value": "x"}]}},
    ],
)
def test_benchmarks_reject_malformed_payloads(assembler, raw):
    with pytest.raises(OpenDotaError, match="Cannot build HeroBenchmarks for hero 1"):
        assembler.normalize_hero_benchmarks(raw, hero_id=1)


# --- Fixtures --------------------------------------------------------------------


@pytest.mark.parametrize("hero_id", [1, 74])
def test_real_payloads_assemble_with_every_value(hero_id, assembler, caplog):
    raw = json.loads((API_FIXTURES / f"hero_{hero_id}_benchmarks.json").read_text())

    with caplog.at_level(logging.DEBUG, logger="opendota_sdk"):
        result = assembler.normalize_hero_benchmarks(raw, hero_id=hero_id)

    assert caplog.records == [], "every metric has a BenchmarkMetric member"
    assert set(result.metrics) == set(BenchmarkMetric)
    assert not result.is_empty
    for metric, entries in raw["result"].items():
        benchmark = result.get(metric)
        assert benchmark is not None
        assert [(p.percentile, p.value) for p in benchmark.points] == [
            (e["percentile"], e["value"]) for e in entries
        ]
        values = [p.value for p in benchmark.points]
        assert values == sorted(values), "a percentile curve never decreases"


def test_real_unknown_hero_payload_is_empty(assembler):
    raw = json.loads((API_FIXTURES / "hero_99999_benchmarks.json").read_text())

    result = assembler.normalize_hero_benchmarks(raw, hero_id=99999)

    assert result.is_empty
    assert set(result.metrics) == set(BenchmarkMetric)


@pytest.mark.parametrize("hero_id", [1, 74, 99999])
def test_benchmark_metric_has_a_member_for_every_recorded_key(hero_id):
    raw = json.loads((API_FIXTURES / f"hero_{hero_id}_benchmarks.json").read_text())

    missing = sorted(set(raw["result"]) - {m.value for m in BenchmarkMetric})
    assert not missing, f"add a BenchmarkMetric member for: {', '.join(missing)}"


def test_benchmark_metric_member_equals_its_api_key():
    assert BenchmarkMetric.EXPERIENCE_PER_MINUTE == "xp_per_min"
    keyed: dict[str, int] = {BenchmarkMetric.GOLD_PER_MINUTE: 1}
    assert keyed["gold_per_min"] == 1


# --- Client ----------------------------------------------------------------------


def _benchmarks_get(calls=None, delay=0.0, inflight=None, payload=None):
    """`_get` stand-in; optionally records (path, params) and peak concurrency."""

    async def fake_get(path, **kwargs):
        if calls is not None:
            calls.append((path, kwargs.get("params")))
        if inflight is not None:
            inflight["now"] += 1
            inflight["peak"] = max(inflight["peak"], inflight["now"])
        try:
            await asyncio.sleep(delay)
        finally:
            if inflight is not None:
                inflight["now"] -= 1
        if path != "/benchmarks":
            raise AssertionError(f"unexpected path {path}")
        return payload if payload is not None else _payload()

    return fake_get


@pytest.mark.asyncio
async def test_get_hero_benchmarks_requests_the_hero_id():
    calls = []
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_benchmarks_get(calls))

        result = await client._get_hero_benchmarks(hero_id=7)

    assert calls == [("/benchmarks", {"hero_id": 7})]
    assert isinstance(result, HeroBenchmarks)
    assert result.hero_id == 7


@pytest.mark.asyncio
async def test_get_hero_benchmarks_is_cached_per_hero():
    calls = []
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_benchmarks_get(calls))

        first = await client._get_hero_benchmarks(hero_id=1)
        second = await client._get_hero_benchmarks(hero_id=1)
        await client._get_hero_benchmarks(hero_id=2)

    assert first is second
    assert [params["hero_id"] for _, params in calls] == [1, 2]


@pytest.mark.asyncio
async def test_concurrent_benchmarks_calls_for_one_hero_share_one_request():
    calls = []
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_benchmarks_get(calls, delay=0.01))

        results = await asyncio.gather(
            *(client._get_hero_benchmarks(hero_id=1) for _ in range(5))
        )

    assert len(calls) == 1
    assert all(result is results[0] for result in results)


@pytest.mark.asyncio
async def test_different_heroes_fetch_benchmarks_in_parallel_not_in_series():
    """Per-hero locks: one shared lock would serialize these and peak at 1 in flight."""
    calls = []
    inflight = {"now": 0, "peak": 0}
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_benchmarks_get(calls, 0.01, inflight))

        await asyncio.gather(
            *(client._get_hero_benchmarks(hero_id=hero_id) for hero_id in range(1, 6))
        )

    assert len(calls) == 5
    assert inflight["peak"] == 5


@pytest.mark.asyncio
async def test_unknown_hero_benchmarks_is_empty_not_an_error():
    raw = json.loads((API_FIXTURES / "hero_99999_benchmarks.json").read_text())
    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_benchmarks_get(payload=raw))

        result = await client._get_hero_benchmarks(hero_id=99999)

    assert result.is_empty


@pytest.mark.asyncio
async def test_benchmarks_log_their_cache_fill_once(caplog):
    caplog.set_level(logging.DEBUG, logger="opendota_sdk")

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=_benchmarks_get())
        await client._get_hero_benchmarks(hero_id=1)
        await client._get_hero_benchmarks(hero_id=1)

    fills = [
        (r.levelno, r.getMessage())
        for r in caplog.records
        if r.getMessage().startswith("Loaded")
    ]
    assert len(fills) == 1
    level, message = fills[0]
    assert level == logging.DEBUG
    assert message.startswith("Loaded 1 benchmark metrics for hero 1 in ")


# --- Relationship method ---------------------------------------------------------


@pytest.mark.asyncio
async def test_hero_get_benchmarks_outside_client_scope_raises():
    with pytest.raises(OpenDotaError, match="No active OpenDotaAsyncClient"):
        await _hero(1).get_benchmarks()


@pytest.mark.asyncio
async def test_hero_get_benchmarks_delegates_to_active_client():
    """A one-line delegation: the client still owns the fetch, cache, and assembly."""
    async with OpenDotaAsyncClient() as client:
        client._get_hero_benchmarks = AsyncMock(return_value="sentinel")

        result = await _hero(3).get_benchmarks()

    assert result == "sentinel"
    client._get_hero_benchmarks.assert_awaited_once_with(hero_id=3)
