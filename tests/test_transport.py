"""Tests for HTTP transport layer."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import json

import niquests

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._errors import (
    HTTPStatusError,
    RateLimitError,
    ResponseDecodeError,
    TransportError,
)
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import (
    HTTPTransportBase,
    SyncHTTPTransport,
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


@patch("niquests.Session")
def test_sync_request_success_with_auth_headers(mock_session_class):
    """Test successful sync request includes authentication headers."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.json.return_value = {"data": "value"}
    mock_session.request.return_value = mock_response

    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="test_key")
    retry = RetryPolicy(max_retries=0)

    transport = SyncHTTPTransport(config, auth, retry)
    result = transport.request_json("GET", "/heroStats")

    assert result == {"data": "value"}
    call_args = mock_session.request.call_args
    assert call_args[1]["headers"]["X-API-Key"] == "test_key"
    mock_session.request.assert_called_once()


@pytest.mark.parametrize(
    "exception_class",
    [
        niquests.exceptions.ConnectionError,
        niquests.exceptions.Timeout,
    ],
)
@patch("niquests.Session")
def test_sync_request_network_errors(mock_session_class, exception_class):
    """Test sync request raises TransportError on network failures."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_session.request.side_effect = exception_class("Failed")

    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy(max_retries=0)

    transport = SyncHTTPTransport(config, auth, retry)

    with pytest.raises(TransportError):
        transport.request_json("GET", "/heroStats")


@patch("niquests.Session")
def test_sync_request_json_decode_error(mock_session_class):
    """Test sync request raises ResponseDecodeError on invalid JSON."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.json.side_effect = json.JSONDecodeError("error", "", 0)
    mock_session.request.return_value = mock_response

    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy(max_retries=0)

    transport = SyncHTTPTransport(config, auth, retry)

    with pytest.raises(ResponseDecodeError):
        transport.request_json("GET", "/heroStats")


@patch("niquests.Session")
def test_sync_close(mock_session_class):
    """Test sync transport close method."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    config = OpenDotaClientConfig()
    auth = AuthHandler(api_key="key")
    retry = RetryPolicy()

    transport = SyncHTTPTransport(config, auth, retry)
    transport.close()

    mock_session.close.assert_called_once()


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
