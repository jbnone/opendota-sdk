"""Tests for retry policy."""

from opendota_sdk.http._retry import RetryPolicy, build_retry_decorator


def test_build_retry_decorator_returns_retrying_object():
    """Test that build_retry_decorator returns a Retrying object with expected interface."""
    policy = RetryPolicy(max_retries=3, backoff_factor=0.5)
    decorator = build_retry_decorator(policy)

    assert hasattr(decorator, "__call__")
    assert hasattr(decorator, "stop")
    assert hasattr(decorator, "wait")
    assert hasattr(decorator, "retry")
