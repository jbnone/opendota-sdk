"""Tests for HTTP transport layer."""

import pytest
from unittest.mock import MagicMock, patch, Mock


from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._errors import (
    HTTPStatusError,
    RateLimitError,
)
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import (
    HTTPTransportBase,
    AsyncHTTPTransport,
)


@pytest.mark.parametrize(
    "base_url,path,expected",
    [
        (
            "https://api.opendota.com/api/",
            "/heroStats",
            "https://api.opendota.com/api/heroStats",
        ),
        (
            "https://api.opendota.com/api",
            "/heroStats",
            "https://api.opendota.com/api/heroStats",
        ),
        (
            "https://api.opendota.com/api",
            "heroStats",
            "https://api.opendota.com/api/heroStats",
        ),
    ],
)
def test_build_url(base_url, path, expected):
    """Test URL building with different base URLs and paths."""
    config = OpenDotaClientConfig(base_url=base_url)
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy()
    transport = HTTPTransportBase(config, auth, retry)

    url = transport.build_url(path)

    assert url == expected


def test_build_headers_defaults_and_config():
    """Test header building with defaults and config extra headers."""
    config = OpenDotaClientConfig(extra_headers={"X-Custom": "value"})
    auth = AuthHandler(api_key="test_key")
    retry = RetryPolicy()
    transport = HTTPTransportBase(config, auth, retry)

    headers = transport.build_headers()

    assert headers["Accept"] == "application/json"
    assert headers["X-Custom"] == "value"
    assert headers["X-API-Key"] == "test_key"


def test_build_headers_with_request_headers():
    """Test header building with additional request headers."""
    config = OpenDotaClientConfig(extra_headers={"X-Custom": "value"})
    auth = AuthHandler(api_key="test_key")
    retry = RetryPolicy()
    transport = HTTPTransportBase(config, auth, retry)

    headers = transport.build_headers(request_headers={"X-Request": "header"})

    assert headers["Accept"] == "application/json"
    assert headers["X-Custom"] == "value"
    assert headers["X-Request"] == "header"
    assert headers["X-API-Key"] == "test_key"


def test_build_headers_request_overrides_config():
    """Test that request headers override config headers."""
    config = OpenDotaClientConfig(extra_headers={"X-Custom": "config_value"})
    auth = AuthHandler(api_key="test_key")
    retry = RetryPolicy()
    transport = HTTPTransportBase(config, auth, retry)

    headers = transport.build_headers(request_headers={"X-Custom": "request_value"})

    assert headers["X-Custom"] == "request_value"


def test_handle_response_200_success():
    """Test handle_response returns response on 200."""
    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy()
    transport = HTTPTransportBase(config, auth, retry)

    response = Mock()
    response.status_code = 200
    response.ok = True

    result = transport.handle_response(response, "GET")

    assert result == response


@pytest.mark.parametrize(
    "status_code,expected_exception",
    [
        (429, RateLimitError),
        (500, HTTPStatusError),
        (404, HTTPStatusError),
    ],
)
def test_handle_response_error_status_codes(status_code, expected_exception):
    """Test handle_response raises appropriate errors for different status codes."""
    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy()
    transport = HTTPTransportBase(config, auth, retry)

    response = Mock()
    response.status_code = status_code
    response.ok = False
    response.url = f"https://api.opendota.com/api/test{status_code}"
    response.text = f"Error {status_code}"
    response.headers = {}

    with pytest.raises(expected_exception):
        transport.handle_response(response, "GET")


@pytest.mark.asyncio
async def test_async_request_success():
    """Test successful async request."""
    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy(max_retries=0)

    with patch("opendota_sdk.http._transport.niquests.AsyncSession"):
        transport = AsyncHTTPTransport(config, auth, retry)

        mock_session = MagicMock()
        transport._session = mock_session

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json = MagicMock(return_value={"data": "value"})

        async def async_request(*args, **kwargs):
            return mock_response

        mock_session.request = async_request

        result = await transport.request_json("GET", "/test")

        assert result == {"data": "value"}


@pytest.mark.asyncio
async def test_async_close():
    """Test async transport close method."""
    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy()

    with patch("opendota_sdk.http._transport.niquests.AsyncSession"):
        transport = AsyncHTTPTransport(config, auth, retry)

        close_called = []

        async def mock_close():
            close_called.append(True)

        transport._session.close = mock_close

        await transport.close()

        assert len(close_called) > 0
