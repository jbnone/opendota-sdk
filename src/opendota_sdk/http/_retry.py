"""Retry policy and decorator builder for HTTP requests."""

from dataclasses import dataclass, field

from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

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
    """

    max_retries: int = 3
    backoff_factor: float = 0.5
    retry_on_status: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    retry_on_timeout: bool = True


def build_retry_decorator(policy: RetryPolicy) -> AsyncRetrying:
    """Build a tenacity `AsyncRetrying` object from a retry policy.

    The transport surfaces every failure as a typed SDK error before the retry
    layer sees it, so retries are decided from the raised exception rather than
    from a returned response. A retry is triggered when:

    - `HTTPStatusError` carries a status code listed in `retry_on_status`
    - `RateLimitError` is raised and 429 is listed in `retry_on_status`
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
            return _RATE_LIMIT_STATUS in policy.retry_on_status
        if isinstance(exc, HTTPStatusError):
            return exc.status_code in policy.retry_on_status
        if isinstance(exc, TransportError):
            return policy.retry_on_timeout if exc.is_timeout else True
        return False

    return AsyncRetrying(
        stop=stop_after_attempt(policy.max_retries),
        wait=wait_exponential(multiplier=policy.backoff_factor, min=0, max=60),
        retry=retry_if_exception(should_retry),
        reraise=True,
    )
