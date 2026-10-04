"""Retry policy and decorator builder for HTTP requests."""

from dataclasses import dataclass, field

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.wait import wait_base

from opendota_sdk._errors import HTTPStatusError, RateLimitError, TransportError

_RATE_LIMIT_STATUS = 429


@dataclass
class RetryPolicy:
    """Policy for retrying failed HTTP requests.

    Attributes:
        max_retries: Maximum number of attempts (total, including initial).
        backoff_factor: Multiplier for exponential backoff wait time. `0` disables
            waiting between attempts entirely.
        retry_on_status: HTTP status codes that should trigger a retry.
        retry_on_timeout: Whether to retry when a request times out.
        max_retry_after: Longest rate-limit wait, in seconds, worth retrying after.
            A 429 asking for longer is raised instead.
    """

    max_retries: int = 3
    backoff_factor: float = 0.5
    retry_on_status: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    retry_on_timeout: bool = True
    max_retry_after: float = 120.0


def is_retryable_rate_limit(policy: RetryPolicy, exc: RateLimitError) -> bool:
    """Decide whether a rate-limited request should be retried under `policy`.

    The single source of truth for both the retry predicate and the transport's
    shared cooldown, so a 429 never triggers a client-wide wait for a request that
    will not itself be retried.

    Args:
        policy: The retry policy in force.
        exc: The rate-limit error raised for the request.

    Returns:
        `False` for the daily quota, when 429 is not in `retry_on_status`, or when the
        requested wait exceeds `max_retry_after`; `True` otherwise.
    """
    if _RATE_LIMIT_STATUS not in policy.retry_on_status or exc.is_daily_limit:
        return False
    return exc.retry_after is None or exc.retry_after <= policy.max_retry_after


class _RateLimitAwareWait(wait_base):
    """Exponential backoff, except after a rate limit that says how long to wait.

    That wait is not taken here: the transport records it as a cooldown deadline
    shared by every request on the client, and each attempt sits it out before
    sending. The backoff for that case is zero so the server's timing governs: any
    backoff would overlap the cooldown rather than add to it, but once it outgrew the
    remaining cooldown it would hold the retry past the moment the limit cleared.
    """

    def __init__(self, backoff: wait_base) -> None:
        self.backoff = backoff

    def __call__(self, retry_state: RetryCallState) -> float:
        outcome = retry_state.outcome
        exc = outcome.exception() if outcome is not None and outcome.failed else None
        if isinstance(exc, RateLimitError) and exc.retry_after is not None:
            return 0.0
        return self.backoff(retry_state)


def build_retry_decorator(policy: RetryPolicy) -> AsyncRetrying:
    """Build a tenacity `AsyncRetrying` object from a retry policy.

    The transport surfaces every failure as a typed SDK error before the retry
    layer sees it, so retries are decided from the raised exception rather than
    from a returned response. A retry is triggered when:

    - `HTTPStatusError` carries a status code listed in `retry_on_status`
    - `RateLimitError` is raised, 429 is listed in `retry_on_status`, it is not the
      daily quota, and any wait it asks for is within `max_retry_after`
    - `TransportError` reports a connection failure, or reports a timeout while
      `retry_on_timeout` is set

    Tenacity keeps some state on the returned object -- notably `statistics`,
    which concurrent runs overwrite -- so callers that fan requests out
    concurrently should drive a fresh `AsyncRetrying.copy()` per request rather
    than the object itself.

    Args:
        policy: The retry policy configuration.

    Returns:
        An `AsyncRetrying` object configured according to the policy.
    """

    def should_retry(exc: BaseException) -> bool:
        """Decide whether a raised transport exception is worth another attempt."""
        if isinstance(exc, RateLimitError):
            return is_retryable_rate_limit(policy, exc)
        if isinstance(exc, HTTPStatusError):
            return exc.status_code in policy.retry_on_status
        if isinstance(exc, TransportError):
            return policy.retry_on_timeout if exc.is_timeout else True
        return False

    return AsyncRetrying(
        stop=stop_after_attempt(policy.max_retries),
        wait=_RateLimitAwareWait(
            wait_exponential(multiplier=policy.backoff_factor, min=0, max=60)
        ),
        retry=retry_if_exception(should_retry),
        reraise=True,
    )
