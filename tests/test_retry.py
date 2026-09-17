"""Tests for retry behavior across the retry policy and the async transport.

These drive retries through `AsyncHTTPTransport` rather than through
`build_retry_decorator` alone, because the bug these guard against lived in the
seam between the two: a synchronous `tenacity.Retrying` was handed an async
callable, so it saw an un-awaited coroutine, never matched its retry predicate,
and let the real exception surface outside the retry loop. Counting how many
times the underlying session was actually called is what catches that.
"""

import asyncio
from typing import Any, cast
from unittest.mock import patch

import niquests
import pytest
from tenacity import AsyncRetrying
from tenacity.wait import wait_exponential

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._errors import (
    HTTPStatusError,
    RateLimitError,
    TransportError,
)
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy, build_retry_decorator
from opendota_sdk.http._transport import AsyncHTTPTransport


class FakeResponse:
    """Minimal stand-in for a niquests.Response."""

    def __init__(self, status_code, headers=None, payload=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.url = "https://api.opendota.com/api/test"
        self.headers = headers or {}
        self.text = f"status {status_code}"
        self.content = b""
        self._payload = {} if payload is None else payload

    def json(self):
        return self._payload


class RecordingSession:
    """Async session stand-in replaying a scripted sequence of outcomes.

    Each entry is either a FakeResponse to return or an exception to raise. The
    last entry repeats once the script runs out, so a one-element script means
    "always this". Every call is counted, and that count is the assertion these
    tests actually care about.
    """

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    async def request(self, **kwargs):
        self.calls += 1
        # Yield control so concurrent requests genuinely interleave.
        await asyncio.sleep(0)
        outcome = self._outcomes[min(self.calls - 1, len(self._outcomes) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def close(self):
        return None


def make_transport(outcomes, **policy_kwargs):
    """Build an AsyncHTTPTransport backed by a RecordingSession.

    Defaults to no backoff so the suite stays fast; tests that care about wait
    timing assert on the wait strategy instead of sleeping.
    """
    policy_kwargs.setdefault("backoff_factor", 0.0)
    policy = RetryPolicy(**policy_kwargs)
    with patch("opendota_sdk.http._transport.niquests.AsyncSession"):
        transport = AsyncHTTPTransport(
            OpenDotaClientConfig(), AuthHandler(api_key="key"), policy
        )
    session = RecordingSession(outcomes)
    transport._session = cast(Any, session)
    return transport, session


def test_build_retry_decorator_is_async_aware():
    """The decorator must be able to await the coroutine it retries.

    A synchronous `Retrying` returns the un-awaited coroutine and silently
    performs exactly one attempt; this is the type-level guard against that.
    """
    assert isinstance(build_retry_decorator(RetryPolicy()), AsyncRetrying)


@pytest.mark.asyncio
async def test_retryable_status_is_retried_to_the_attempt_limit():
    """A 503 is attempted max_retries times, then reraised."""
    transport, session = make_transport([FakeResponse(503)], max_retries=3)

    with pytest.raises(HTTPStatusError) as exc_info:
        await transport.request("GET", "/test")

    assert session.calls == 3
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_transient_failure_then_success_returns_the_success():
    """A 503 followed by a 200 resolves without surfacing an error."""
    transport, session = make_transport(
        [FakeResponse(503), FakeResponse(200, payload={"ok": True})], max_retries=3
    )

    result = await transport.request_json("GET", "/test")

    assert result == {"ok": True}
    assert session.calls == 2


@pytest.mark.asyncio
async def test_non_retryable_status_is_not_retried():
    """A 404 is not in retry_on_status, so it fails on the first attempt."""
    transport, session = make_transport([FakeResponse(404)], max_retries=3)

    with pytest.raises(HTTPStatusError):
        await transport.request("GET", "/test")

    assert session.calls == 1


@pytest.mark.asyncio
async def test_rate_limit_is_retried():
    """429 raises RateLimitError rather than returning a response, and still retries."""
    transport, session = make_transport(
        [FakeResponse(429, headers={"Retry-After": "1"})], max_retries=3
    )

    with pytest.raises(RateLimitError) as exc_info:
        await transport.request("GET", "/test")

    assert session.calls == 3
    assert exc_info.value.retry_after == 1


@pytest.mark.asyncio
async def test_rate_limit_not_retried_when_429_excluded():
    """Dropping 429 from retry_on_status turns rate limits into a single attempt."""
    transport, session = make_transport(
        [FakeResponse(429)], max_retries=3, retry_on_status=[500, 502]
    )

    with pytest.raises(RateLimitError):
        await transport.request("GET", "/test")

    assert session.calls == 1


@pytest.mark.asyncio
async def test_connection_error_is_retried():
    """Network failures are transient and retried to the attempt limit."""
    transport, session = make_transport(
        [niquests.ConnectionError("refused")], max_retries=3
    )

    with pytest.raises(TransportError) as exc_info:
        await transport.request("GET", "/test")

    assert session.calls == 3
    assert exc_info.value.is_timeout is False


@pytest.mark.asyncio
async def test_timeout_is_retried_when_enabled():
    """Timeouts are flagged as such and retried while retry_on_timeout is set."""
    transport, session = make_transport(
        [niquests.Timeout("too slow")], max_retries=3, retry_on_timeout=True
    )

    with pytest.raises(TransportError) as exc_info:
        await transport.request("GET", "/test")

    assert session.calls == 3
    assert exc_info.value.is_timeout is True


@pytest.mark.asyncio
async def test_timeout_not_retried_when_disabled():
    """retry_on_timeout=False stops timeouts at one attempt, unlike other failures."""
    transport, session = make_transport(
        [niquests.Timeout("too slow")], max_retries=3, retry_on_timeout=False
    )

    with pytest.raises(TransportError):
        await transport.request("GET", "/test")

    assert session.calls == 1


@pytest.mark.asyncio
async def test_timeout_still_retried_as_transport_failure_is_distinct():
    """A non-timeout transport failure retries even with retry_on_timeout off."""
    transport, session = make_transport(
        [niquests.ConnectionError("refused")], max_retries=3, retry_on_timeout=False
    )

    with pytest.raises(TransportError):
        await transport.request("GET", "/test")

    assert session.calls == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("max_retries,expected_calls", [(0, 1), (1, 1), (2, 2), (5, 5)])
async def test_attempt_count_follows_max_retries(max_retries, expected_calls):
    """max_retries is a total attempt budget, and 0 still makes one attempt."""
    transport, session = make_transport([FakeResponse(500)], max_retries=max_retries)

    with pytest.raises(HTTPStatusError):
        await transport.request("GET", "/test")

    assert session.calls == expected_calls


@pytest.mark.asyncio
async def test_concurrent_requests_each_get_a_full_attempt_budget():
    """Each concurrently-gathered request gets its own full attempt budget.

    `get_heroes()` fans five requests out through one transport with
    asyncio.gather, so this is the shape that actually runs in production.
    Retry bookkeeping is per-call today even on a shared Retrying object, so
    this pins that property rather than reproducing a known failure.
    """
    transport, session = make_transport([FakeResponse(503)], max_retries=3)

    results = await asyncio.gather(
        *(transport.request("GET", "/test") for _ in range(4)),
        return_exceptions=True,
    )

    assert all(isinstance(result, HTTPStatusError) for result in results)
    assert session.calls == 12


@pytest.mark.asyncio
async def test_sequential_requests_each_get_a_full_attempt_budget():
    """Attempt state resets between calls on the same transport."""
    transport, session = make_transport([FakeResponse(503)], max_retries=2)

    for _ in range(3):
        with pytest.raises(HTTPStatusError):
            await transport.request("GET", "/test")

    assert session.calls == 6


@pytest.mark.parametrize(
    "backoff_factor,expected_first_wait", [(0.0, 0.0), (0.5, 1.0), (2.0, 4.0)]
)
def test_backoff_factor_scales_the_wait(backoff_factor, expected_first_wait):
    """backoff_factor drives the wait, and 0 means no wait at all."""
    policy = RetryPolicy(backoff_factor=backoff_factor)
    wait = cast(wait_exponential, build_retry_decorator(policy).wait)

    assert wait.multiplier == backoff_factor
    assert wait.min == 0
    assert wait.multiplier * (2**1) == expected_first_wait
