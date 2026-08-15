"""Shared fixtures for opendota-sdk tests."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def real_items_json() -> dict:
    """Real dotaconstants items payload (tests/fixtures/items.json), shared across item-slice tests."""
    with (FIXTURES_DIR / "items.json").open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def default_config():
    """Return a default configuration for testing."""
    return OpenDotaClientConfig(
        api_key="test_key",
        base_url="https://api.opendota.com/api",
        timeout=10.0,
        max_retries=3,
        backoff_factor=0.5,
        verify_ssl=True,
        trust_env=True,
    )


@pytest.fixture
def auth_handler():
    """Return an auth handler with a test API key."""
    return AuthHandler(api_key="test_key")


@pytest.fixture
def retry_policy():
    """Return a default retry policy."""
    return RetryPolicy(
        max_retries=3,
        backoff_factor=0.5,
        retry_on_status=[429, 500, 502, 503, 504],
    )


@pytest.fixture
def mock_response():
    """Return a mock niquests.Response object."""
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    response.text = '{"test": "data"}'
    response.json.return_value = {"test": "data"}
    return response


@pytest.fixture
def mock_session():
    """Return a mock niquests.Session object."""
    with patch("niquests.Session") as mock:
        yield mock


@pytest.fixture
def mock_retry_decorator():
    """Return a mock retry decorator that does not actually retry."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator
