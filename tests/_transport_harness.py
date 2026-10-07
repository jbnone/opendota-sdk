"""Shared fake-clock harness for driving `AsyncHTTPTransport` in tests.

Used by the retry, rate-limit, and logging tests. It replaces the network session
with a scripted recorder and the transport's clock/sleep seams with a fake clock,
so tests can assert exact attempt counts, timings, and log output without sleeping.
"""

import asyncio
from typing import Any, cast
from unittest.mock import patch

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
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


class FakeClock:
    """Monotonic clock that only advances when the transport sleeps on it.

    Installed as the transport's `_clock`/`_sleep` seams, so rate-limit cooldowns
    can be asserted on exactly without the suite actually waiting.
    """

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay
        await asyncio.sleep(0)


class RecordingSession:
    """Async session stand-in replaying a scripted sequence of outcomes.

    Each entry is either a FakeResponse to return or an exception to raise. The
    last entry repeats once the script runs out, so a one-element script means
    "always this". Every call is counted, and that count is the assertion these
    tests actually care about. It also records the fake-clock time of each send and
    the peak number of requests simultaneously on the wire.
    """

    def __init__(self, outcomes, clock: FakeClock):
        self._outcomes = list(outcomes)
        self.clock = clock
        self.calls = 0
        self.sent_at = []
        self.urls = []
        self.sent_headers = []
        self.inflight = 0
        self.peak_inflight = 0

    async def request(self, **kwargs):
        self.calls += 1
        self.urls.append(kwargs.get("url"))
        self.sent_headers.append(kwargs.get("headers") or {})
        self.sent_at.append(self.clock.now)
        outcome = self._outcomes[min(self.calls - 1, len(self._outcomes) - 1)]
        self.inflight += 1
        self.peak_inflight = max(self.peak_inflight, self.inflight)
        try:
            # Yield control so concurrent requests genuinely interleave.
            await asyncio.sleep(0)
        finally:
            self.inflight -= 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def close(self):
        return None


def make_transport(outcomes, max_concurrency=10, api_key="key", **policy_kwargs):
    """Build an AsyncHTTPTransport backed by a RecordingSession and a FakeClock.

    Defaults to no backoff, and routes rate-limit cooldowns through the fake clock,
    so the suite never really sleeps; tests read `session.clock` for timing.
    """
    policy_kwargs.setdefault("backoff_factor", 0.0)
    policy = RetryPolicy(**policy_kwargs)
    config = OpenDotaClientConfig(max_concurrency=max_concurrency)
    with patch("opendota_sdk.http._transport.niquests.AsyncSession"):
        transport = AsyncHTTPTransport(config, AuthHandler(api_key=api_key), policy)
    clock = FakeClock()
    transport._clock = clock
    transport._sleep = clock.sleep
    session = RecordingSession(outcomes, clock=clock)
    transport._session = cast(Any, session)
    return transport, session
