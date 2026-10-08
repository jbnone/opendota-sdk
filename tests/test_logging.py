"""Tests for what the SDK logs, at which level, and what it must never log.

The contract (AGENTS.md §10.6): DEBUG for per-attempt and cache-fill detail, INFO for
retries and rate-limit pauses, WARNING only for data problems the caller cannot see
otherwise. Nothing the SDK raises is also logged at WARNING or above, the library
installs no handlers, and secrets, headers, and bodies never reach a log line.
"""

import asyncio
import logging
from typing import Any, cast
from unittest.mock import AsyncMock

import niquests
import pytest

from opendota_sdk import OpenDotaAsyncClient
from opendota_sdk._errors import HTTPStatusError, RateLimitError
from tests._transport_harness import FakeResponse, make_transport

SDK_LOGGER = "opendota_sdk"

_MINUTE_LIMITED = {
    "X-Rate-Limit-Remaining-Minute": "-1",
    "Date": "Sun, 04 Oct 2026 12:00:45 GMT",
}


@pytest.fixture
def sdk_logs(caplog):
    caplog.set_level(logging.DEBUG, logger=SDK_LOGGER)
    return caplog


def messages(caplog, level=None):
    return [
        record.getMessage()
        for record in caplog.records
        if level is None or record.levelno == level
    ]


def test_library_installs_no_handlers():
    """Configuring output is the application's job, never the library's."""
    sdk_logger = logging.getLogger(SDK_LOGGER)

    assert sdk_logger.handlers == []
    assert sdk_logger.propagate is True


@pytest.mark.asyncio
async def test_successful_request_logs_one_debug_line_and_nothing_louder(sdk_logs):
    transport, _ = make_transport([FakeResponse(200)])

    await transport.request("GET", "/heroStats")

    assert messages(sdk_logs) == ["GET /heroStats -> 200 in 0.00s (attempt 1)"]
    assert all(record.levelno == logging.DEBUG for record in sdk_logs.records)


@pytest.mark.asyncio
async def test_retry_is_logged_at_info_with_cause_and_wait(sdk_logs):
    transport, _ = make_transport(
        [FakeResponse(503), FakeResponse(200)], backoff_factor=0.5
    )

    await transport.request("GET", "/heroStats")

    assert messages(sdk_logs, logging.INFO) == [
        "Retrying GET /heroStats after HTTP 503 (attempt 1 of 3) in 0.50s"
    ]
    assert messages(sdk_logs, logging.DEBUG) == [
        "GET /heroStats -> 503 in 0.00s (attempt 1)",
        "GET /heroStats -> 200 in 0.00s (attempt 2)",
    ]


@pytest.mark.asyncio
async def test_timeout_is_logged_without_echoing_the_exception_text(sdk_logs):
    transport, _ = make_transport(
        [
            niquests.Timeout("https://api.opendota.com/api/x?api_key=leak"),
            FakeResponse(200),
        ]
    )

    await transport.request("GET", "/x")

    assert "GET /x timed out after 0.00s (attempt 1)" in messages(sdk_logs)
    assert "Retrying GET /x after timeout (attempt 1 of 3) in 0.00s" in messages(
        sdk_logs
    )
    assert "leak" not in sdk_logs.text


@pytest.mark.asyncio
async def test_rate_limit_pause_is_logged_once_with_its_length(sdk_logs):
    """A burst of concurrent 429s is one pause, so it is one INFO line, not five."""
    transport, _ = make_transport(
        [FakeResponse(429, headers=_MINUTE_LIMITED)] * 5 + [FakeResponse(200)]
    )

    await asyncio.gather(*(transport.request("GET", "/x") for _ in range(5)))

    pauses = [
        m for m in messages(sdk_logs, logging.INFO) if m.startswith("Rate limited")
    ]
    assert pauses == [
        "Rate limited on GET /x; holding all requests on this client for 16s"
    ]
    assert (
        "Retrying GET /x after rate limit (HTTP 429) (attempt 1 of 3) once the limit "
        "clears" in messages(sdk_logs, logging.INFO)
    )


@pytest.mark.asyncio
async def test_cooldown_wait_is_logged_at_debug(sdk_logs):
    transport, _ = make_transport(
        [FakeResponse(429, headers=_MINUTE_LIMITED), FakeResponse(200)]
    )

    await transport.request("GET", "/x")

    assert "GET /x: waiting 16.0s for the rate-limit cooldown" in messages(
        sdk_logs, logging.DEBUG
    )


@pytest.mark.asyncio
async def test_failures_the_caller_receives_are_not_logged_loudly(sdk_logs):
    """An error the SDK raises is the caller's to report; logging it too duplicates it."""
    transport, _ = make_transport([FakeResponse(404)])
    with pytest.raises(HTTPStatusError):
        await transport.request("GET", "/missing")

    daily, _ = make_transport(
        [FakeResponse(429, headers={"X-Rate-Limit-Remaining-Day": "-1"})]
    )
    with pytest.raises(RateLimitError):
        await daily.request("GET", "/x")

    assert all(record.levelno == logging.DEBUG for record in sdk_logs.records)


@pytest.mark.asyncio
async def test_api_key_never_reaches_a_log_line(sdk_logs):
    """Covers the header the key travels in today and a query param it could use."""
    secret = "SECRET-KEY-0123456789"
    transport, _ = make_transport(
        [
            FakeResponse(503),
            FakeResponse(429, headers=_MINUTE_LIMITED),
            niquests.ConnectionError(f"refused for {secret}"),
            FakeResponse(200),
        ],
        api_key=secret,
        max_retries=4,
    )

    await transport.request("GET", "/x", params={"api_key": secret, "limit": 5})

    assert sdk_logs.records, "expected log output to inspect"
    assert secret not in sdk_logs.text
    for record in sdk_logs.records:
        assert secret not in record.getMessage()
        assert all(secret not in str(arg) for arg in record.args or ())
    assert "GET /x?api_key=***&limit=5 -> 200" in sdk_logs.text


@pytest.mark.asyncio
async def test_client_logs_each_cache_fill_once_and_cache_hits_not_at_all(sdk_logs):
    items_payload = {"blink": {"id": 1, "dname": "Blink Dagger", "cost": 2250}}

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(return_value=items_payload)
        await client.get_items()
        await client.get_items()
        await client.get_item(item_name="blink")

    fills = [m for m in messages(sdk_logs) if m.startswith("Loaded")]
    assert len(fills) == 1
    assert fills[0].startswith("Loaded 1 items in ")
    assert fills[0].endswith("; cached on client")


def test_hero_merge_warning_uses_lazy_arguments(sdk_logs):
    """Data problems are WARNING, and formatted lazily (enforced by ruff G/LOG too)."""
    OpenDotaAsyncClient._make_heroes(
        heroes_api=[{"id": 999, "name": "npc_dota_hero_nobody"}],
        heroes_constants={},
        hero_abilities={},
        abilities={},
        hero_lore={},
        assembler=cast(Any, _PermissiveAssembler()),
    )

    warnings = [r for r in sdk_logs.records if r.levelno == logging.WARNING]
    assert [r.getMessage() for r in warnings] == [
        "Hero id 999 from /heroes not found in /constants/heroes; using API data only",
        (
            "Hero name 'npc_dota_hero_nobody' not found in /constants/hero_abilities; "
            "it will have no abilities or talents"
        ),
    ]
    assert all(r.args for r in warnings)


class _PermissiveAssembler:
    """Stand-in so the merge warnings can be observed without a valid hero payload."""

    def normalize_hero(self, merged, abilities_by_name):
        return merged


@pytest.mark.asyncio
async def test_item_popularity_logs_its_cache_fill_once(sdk_logs):
    items = {"branches": {"id": 16, "dname": "Iron Branch", "cost": 50}}
    payload = {"start_game_items": {"16": 3}}

    async def fake_get(path, **kwargs):
        return items if path == "/constants/items" else payload

    async with OpenDotaAsyncClient() as client:
        client._get = AsyncMock(side_effect=fake_get)
        await client.get_hero_item_popularity(hero_id=1)
        await client.get_hero_item_popularity(hero_id=1)

    fills = [m for m in messages(sdk_logs) if "item popularity" in m]
    assert len(fills) == 1
    assert fills[0].startswith(
        "Loaded item popularity for hero 1 (1 items across 4 phases) in "
    )
