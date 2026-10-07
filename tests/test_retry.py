"""Tests for retry behavior across the retry policy and the async transport.

These drive retries through `AsyncHTTPTransport` rather than through
`build_retry_decorator` alone, because the bug these guard against lived in the
seam between the two: a synchronous `tenacity.Retrying` was handed an async
callable, so it saw an un-awaited coroutine, never matched its retry predicate,
and let the real exception surface outside the retry loop. Counting how many
times the underlying session was actually called is what catches that.
"""

import asyncio

import niquests
import pytest
from tenacity import AsyncRetrying, Future, RetryCallState

from opendota_sdk._errors import (
    HTTPStatusError,
    RateLimitError,
    TransportError,
)
from opendota_sdk.http._retry import RetryPolicy, build_retry_decorator
from tests._transport_harness import FakeResponse, make_transport


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


def wait_after(policy, exc, attempt):
    """The wait tenacity would actually take after `attempt` failed with `exc`."""
    retrying = build_retry_decorator(policy)
    state = RetryCallState(retrying, None, (), {})
    state.attempt_number = attempt
    state.outcome = Future.construct(attempt, exc, True)
    return retrying.wait(state)


@pytest.mark.parametrize(
    "backoff_factor,expected_waits",
    [(0.0, [0.0, 0.0, 0.0]), (0.5, [0.5, 1.0, 2.0]), (2.0, [2.0, 4.0, 8.0])],
)
def test_backoff_factor_scales_the_wait(backoff_factor, expected_waits):
    """backoff_factor drives the wait, and 0 means no wait at all.

    Expected values come from tenacity itself, not hand arithmetic: an earlier
    version computed them by hand and so never noticed the first wait at the
    default factor dropped from 1.0s to 0.5s when `min=1` became `min=0`.
    """
    policy = RetryPolicy(backoff_factor=backoff_factor)
    exc = HTTPStatusError(503, "GET", "https://api.opendota.com/api/test")

    waits = [wait_after(policy, exc, attempt) for attempt in (1, 2, 3)]

    assert waits == expected_waits


def test_backoff_is_capped_at_sixty_seconds():
    policy = RetryPolicy(backoff_factor=10.0)
    exc = HTTPStatusError(503, "GET", "https://api.opendota.com/api/test")

    assert wait_after(policy, exc, 10) == 60


# --- Concurrency cap -------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrency_cap_bounds_requests_in_flight():
    transport, session = make_transport([FakeResponse(200)], max_concurrency=3)

    await asyncio.gather(*(transport.request("GET", "/test") for _ in range(20)))

    assert session.calls == 20
    assert session.peak_inflight == 3


@pytest.mark.asyncio
async def test_concurrency_cap_of_one_serializes_requests():
    transport, session = make_transport([FakeResponse(200)], max_concurrency=1)

    await asyncio.gather(*(transport.request("GET", "/test") for _ in range(5)))

    assert session.peak_inflight == 1


@pytest.mark.asyncio
async def test_without_a_tight_cap_requests_do_run_concurrently():
    """Guards the cap tests above: the harness can observe real overlap."""
    transport, session = make_transport([FakeResponse(200)], max_concurrency=10)

    await asyncio.gather(*(transport.request("GET", "/test") for _ in range(5)))

    assert session.peak_inflight == 5


@pytest.mark.asyncio
async def test_backoff_does_not_hold_a_concurrency_slot():
    """A retry that is only backing off must let other requests through.

    With one slot, A fails, and while A sleeps out its backoff B is sent. If the
    slot were held across the backoff, B would wait for A's retry to finish.
    """
    transport, session = make_transport(
        [FakeResponse(503), FakeResponse(200), FakeResponse(200)],
        max_concurrency=1,
        backoff_factor=1.0,
    )

    await asyncio.gather(transport.request("GET", "/a"), transport.request("GET", "/b"))

    assert [url.rsplit("/", 1)[-1] for url in session.urls] == ["a", "b", "a"]


# --- Rate limiting ---------------------------------------------------------------

_MINUTE_LIMITED = {
    "X-Rate-Limit-Remaining-Minute": "-1",
    "Date": "Sun, 04 Oct 2026 12:00:45 GMT",
}


@pytest.mark.asyncio
async def test_minute_limit_waits_for_the_window_to_reset():
    """OpenDota sends no Retry-After; the wait is the time to the next minute."""
    transport, session = make_transport(
        [FakeResponse(429, headers=_MINUTE_LIMITED), FakeResponse(200)],
        backoff_factor=1.0,
    )

    await transport.request("GET", "/test")

    assert session.sent_at == [0.0, 16.0]


@pytest.mark.asyncio
async def test_rate_limit_retry_follows_server_timing_not_backoff():
    """The retry goes out when the limit clears, even if backoff would wait longer.

    Backoff here would be 60s; the window clears in 16s. The cooldown is an absolute
    deadline, so a shorter backoff would merely overlap it -- only a longer one shows
    the difference, which is why the factor is deliberately huge.
    """
    transport, session = make_transport(
        [FakeResponse(429, headers=_MINUTE_LIMITED), FakeResponse(200)],
        backoff_factor=100.0,
    )

    await transport.request("GET", "/test")

    assert session.sent_at == [0.0, 16.0]
    assert session.clock.sleeps == [0.0, 16.0]


@pytest.mark.asyncio
async def test_rate_limit_cooldown_holds_every_request_on_the_client():
    """One 429 pauses the whole client, not just the request that received it.

    OpenDota counts per key or IP, so a request sent during the cooldown would only
    be rejected too, and would burn one of its own attempts doing it.
    """
    transport, session = make_transport(
        [FakeResponse(429, headers=_MINUTE_LIMITED), FakeResponse(200)],
        max_concurrency=1,
    )

    results = await asyncio.gather(
        transport.request("GET", "/a"), transport.request("GET", "/b")
    )

    assert session.sent_at == [0.0, 16.0, 16.0]
    assert all(result.status_code == 200 for result in results)


@pytest.mark.asyncio
async def test_daily_limit_is_raised_without_retry_or_cooldown():
    transport, session = make_transport(
        [FakeResponse(429, headers={"X-Rate-Limit-Remaining-Day": "-1"})],
        max_retries=3,
    )

    with pytest.raises(RateLimitError) as exc_info:
        await transport.request("GET", "/test")

    assert session.calls == 1
    assert exc_info.value.is_daily_limit is True
    assert transport._resume_at == 0.0


@pytest.mark.asyncio
async def test_retry_after_beyond_the_cap_is_raised_without_retry_or_cooldown():
    """A server asking for an hour should not silently stall a batch for an hour."""
    transport, session = make_transport(
        [FakeResponse(429, headers={"Retry-After": "3600"})],
        max_retries=3,
        max_retry_after=120.0,
    )

    with pytest.raises(RateLimitError) as exc_info:
        await transport.request("GET", "/test")

    assert session.calls == 1
    assert exc_info.value.retry_after == 3600
    assert transport._resume_at == 0.0


@pytest.mark.asyncio
async def test_no_cooldown_when_429s_are_not_retried():
    """A policy that fails fast on 429 must not make other requests wait either."""
    transport, _ = make_transport(
        [FakeResponse(429, headers=_MINUTE_LIMITED)], retry_on_status=[500]
    )

    with pytest.raises(RateLimitError):
        await transport.request("GET", "/test")

    assert transport._resume_at == 0.0


@pytest.mark.asyncio
async def test_429_of_unknown_origin_falls_back_to_exponential_backoff():
    """With no Retry-After and no OpenDota headers, there is no window to wait for."""
    transport, session = make_transport([FakeResponse(429)], max_retries=3)

    with pytest.raises(RateLimitError) as exc_info:
        await transport.request("GET", "/test")

    assert session.calls == 3
    assert exc_info.value.retry_after is None
    assert transport._resume_at == 0.0
