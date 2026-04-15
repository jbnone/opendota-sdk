"""Retry policy and decorator builder for HTTP requests."""

from dataclasses import dataclass, field
from typing import Any

from tenacity import (
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)


@dataclass
class RetryPolicy:
    """Policy for retrying failed HTTP requests.

    Attributes:
        max_retries: Maximum number of attempts (total, including initial).
        backoff_factor: Multiplier for exponential backoff wait time.
        retry_on_status: HTTP status codes that should trigger a retry.
        retry_on_timeout: Whether to retry on timeout exceptions.
    """

    max_retries: int = 3
    backoff_factor: float = 0.5
    retry_on_status: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    retry_on_timeout: bool = True


def build_retry_decorator(policy: RetryPolicy) -> Retrying:
    """Build a tenacity Retrying object from a retry policy.

    The returned object can be used as a decorator or context manager to retry
    a callable with exponential backoff. Retries are triggered when:
    - The response status code is in retry_on_status
    - A timeout exception occurs (if retry_on_timeout is True)

    Args:
        policy: The retry policy configuration.

    Returns:
        A tenacity.Retrying object configured according to the policy.
    """

    def should_retry(result: Any) -> bool:
        """Check if response should be retried based on status code."""
        if hasattr(result, "status_code"):
            return result.status_code in policy.retry_on_status
        return False

    retry_decorator = Retrying(
        stop=stop_after_attempt(policy.max_retries),
        wait=wait_exponential(multiplier=policy.backoff_factor, min=1, max=60),
        retry=retry_if_result(should_retry),
        reraise=True,
    )

    if policy.retry_on_timeout:
        retry_decorator = Retrying(
            stop=stop_after_attempt(policy.max_retries),
            wait=wait_exponential(multiplier=policy.backoff_factor, min=1, max=60),
            retry=(
                retry_if_result(should_retry) | retry_if_exception_type(TimeoutError)
            ),
            reraise=True,
        )

    return retry_decorator
