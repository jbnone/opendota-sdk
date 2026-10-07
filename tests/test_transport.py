"""Tests for HTTP transport layer."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from opendota_sdk._config import OpenDotaClientConfig
from opendota_sdk._errors import (
    HTTPStatusError,
    RateLimitError,
)
from opendota_sdk.http._auth import AuthHandler
from opendota_sdk.http._retry import RetryPolicy
from opendota_sdk.http._transport import (
    AsyncHTTPTransport,
    HTTPTransportBase,
    _rate_limit_details,
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
    assert headers["Authorization"] == "Bearer test_key"
    assert "X-API-Key" not in headers


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
    assert headers["Authorization"] == "Bearer test_key"
    assert "X-API-Key" not in headers


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

        mock_close = AsyncMock()
        transport._session.close = mock_close

        await transport.close()

        mock_close.assert_called_once()


_SERVER_DATE = "Sun, 04 Oct 2026 12:00:45 GMT"


@pytest.mark.parametrize(
    "headers,expected",
    [
        # Explicit Retry-After, as a proxy in front of OpenDota might send.
        ({"Retry-After": "7"}, (7, False)),
        ({"Retry-After": " 7 "}, (7, False)),
        ({"Retry-After": "-3"}, (0, False)),
        # HTTP-date form is measured against the server's Date, not the local clock.
        (
            {"Retry-After": "Sun, 04 Oct 2026 12:01:15 GMT", "Date": _SERVER_DATE},
            (30, False),
        ),
        (
            {"Retry-After": "Sun, 04 Oct 2026 12:00:00 GMT", "Date": _SERVER_DATE},
            (0, False),
        ),
        # OpenDota's own minute limit: wait for the next minute boundary, plus margin.
        (
            {"X-Rate-Limit-Remaining-Minute": "-1", "Date": _SERVER_DATE},
            (16, False),
        ),
        (
            {
                "x-rate-limit-remaining-minute": "-4",
                "date": "Sun, 04 Oct 2026 12:00:00 GMT",
            },
            (61, False),
        ),
        # Daily quota cannot be waited out, and wins over everything else.
        (
            {"X-Rate-Limit-Remaining-Day": "-1", "X-Rate-Limit-Remaining-Minute": "-1"},
            (None, True),
        ),
        ({"x-rate-limit-remaining-day": "-1", "Retry-After": "5"}, (None, True)),
        # A non-negative remaining-minute means OpenDota's limiter did not reject this,
        # so there is no window to wait for.
        ({"X-Rate-Limit-Remaining-Minute": "12", "Date": _SERVER_DATE}, (None, False)),
        # Nothing usable: leave it to ordinary exponential backoff.
        ({}, (None, False)),
        ({"Retry-After": "soon"}, (None, False)),
        ({"X-Rate-Limit-Remaining-Day": "lots"}, (None, False)),
    ],
)
def test_rate_limit_details(headers, expected):
    assert _rate_limit_details(headers) == expected


def test_handle_response_429_carries_parsed_rate_limit_details():
    transport = HTTPTransportBase(
        OpenDotaClientConfig(), AuthHandler(api_key="key"), RetryPolicy()
    )
    response = Mock()
    response.status_code = 429
    response.ok = False
    response.url = "https://api.opendota.com/api/heroes"
    response.headers = {"X-Rate-Limit-Remaining-Minute": "-1", "Date": _SERVER_DATE}

    with pytest.raises(RateLimitError) as exc_info:
        transport.handle_response(response, "GET")

    assert exc_info.value.retry_after == 16
    assert exc_info.value.is_daily_limit is False


def test_handle_response_daily_429_is_flagged():
    transport = HTTPTransportBase(
        OpenDotaClientConfig(), AuthHandler(api_key="key"), RetryPolicy()
    )
    response = Mock()
    response.status_code = 429
    response.ok = False
    response.url = "https://api.opendota.com/api/heroes"
    response.headers = {"X-Rate-Limit-Remaining-Day": "-1"}

    with pytest.raises(RateLimitError, match="Daily request limit") as exc_info:
        transport.handle_response(response, "GET")

    assert exc_info.value.is_daily_limit is True
    assert exc_info.value.retry_after is None


@pytest.mark.parametrize("max_concurrency", [0, -1])
def test_async_transport_rejects_non_positive_concurrency(max_concurrency):
    config = OpenDotaClientConfig(max_concurrency=max_concurrency)

    with (
        patch("opendota_sdk.http._transport.niquests.AsyncSession"),
        pytest.raises(ValueError, match="max_concurrency must be at least 1"),
    ):
        AsyncHTTPTransport(config, AuthHandler(api_key="key"), RetryPolicy())


@pytest.mark.parametrize(
    "kwargs,expected_message",
    [
        ({}, "Rate limited."),
        ({"retry_after": 16}, "Rate limited. Retry after 16 seconds."),
        ({"retry_after": 16, "is_daily_limit": True}, "Daily request limit exceeded."),
        ({"message": "custom"}, "custom"),
    ],
)
def test_rate_limit_error_default_messages(kwargs, expected_message):
    assert str(RateLimitError(**kwargs)) == expected_message
