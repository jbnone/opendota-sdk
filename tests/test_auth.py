"""Tests for authentication handler.

OpenDota reads the API key only from `Authorization: Bearer <key>` (or `?api_key=`); any
other header is silently ignored. These tests pin the exact header and value, because the
SDK once sent `X-API-Key` and every keyed user was quietly served as anonymous.
"""

import os
from typing import Any, cast
from unittest.mock import patch

import pytest

from opendota_sdk import HTTPStatusError, InvalidAPIKeyError, OpenDotaAsyncClient
from opendota_sdk.http._auth import AuthHandler
from tests._transport_harness import (
    FakeClock,
    FakeResponse,
    RecordingSession,
    make_transport,
)

KEY = "0f1e2d3c-4b5a-4978-8a69-5b4c3d2e1f00"


def test_init_with_api_key():
    assert AuthHandler(api_key=KEY).api_key == KEY


def test_init_reads_from_env():
    with patch.dict(os.environ, {"OPENDOTA_API_KEY": KEY}):
        assert AuthHandler().api_key == KEY


def test_init_api_key_takes_precedence_over_env():
    with patch.dict(os.environ, {"OPENDOTA_API_KEY": "env_key"}):
        assert AuthHandler(api_key="explicit_key").api_key == "explicit_key"


def test_init_no_api_key_no_env():
    with patch.dict(os.environ, {}, clear=True):
        assert AuthHandler().api_key is None


@pytest.mark.parametrize("raw", [f"{KEY}\n", f"  {KEY}  ", f"\t{KEY}\r\n"])
def test_surrounding_whitespace_is_stripped(raw):
    """A trailing newline from a secrets file would otherwise fail OpenDota's format check."""
    with patch.dict(os.environ, {"OPENDOTA_API_KEY": raw}):
        assert AuthHandler().api_key == KEY
    assert AuthHandler(api_key=raw).api_key == KEY


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_blank_key_means_anonymous(blank):
    with patch.dict(os.environ, {}, clear=True):
        handler = AuthHandler(api_key=blank)

    assert handler.api_key is None
    assert handler.apply_to_headers({"Accept": "application/json"}) == {
        "Accept": "application/json"
    }


def test_key_is_sent_as_a_bearer_token():
    headers = AuthHandler(api_key=KEY).apply_to_headers({"Accept": "application/json"})

    assert headers == {"Accept": "application/json", "Authorization": f"Bearer {KEY}"}


def test_key_is_never_sent_in_a_header_opendota_ignores():
    headers = AuthHandler(api_key=KEY).apply_to_headers({})

    assert "X-API-Key" not in headers
    assert list(headers) == ["Authorization"]


def test_configured_key_replaces_an_existing_authorization_header():
    headers = AuthHandler(api_key=KEY).apply_to_headers({"Authorization": "Bearer old"})

    assert headers["Authorization"] == f"Bearer {KEY}"


def test_apply_to_headers_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        handler = AuthHandler(api_key=None)

    headers = {"Accept": "application/json"}
    assert handler.apply_to_headers(headers) == {"Accept": "application/json"}


def test_apply_to_headers_does_not_mutate_original():
    headers = {"Accept": "application/json"}

    result = AuthHandler(api_key=KEY).apply_to_headers(headers)

    assert "Authorization" not in headers
    assert result["Authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize("api_key,expected", [(KEY, True), (None, False)])
def test_has_auth(api_key, expected):
    with patch.dict(os.environ, {}, clear=True):
        assert AuthHandler(api_key=api_key).has_auth() is expected


@pytest.mark.asyncio
async def test_client_api_key_reaches_the_wire_as_a_bearer_token():
    """End to end: the header the session is actually handed, via the public client."""
    async with OpenDotaAsyncClient(api_key=f"{KEY}\n") as client:
        session = RecordingSession([FakeResponse(200, payload=[])], clock=FakeClock())
        client._transport._session = cast(Any, session)
        await client._get("/heroStats")

    sent = session.sent_headers[0]
    assert sent["Authorization"] == f"Bearer {KEY}"
    assert "X-API-Key" not in sent


@pytest.mark.asyncio
async def test_anonymous_client_sends_no_authorization_header():
    with patch.dict(os.environ, {}, clear=True):
        client = OpenDotaAsyncClient()
    async with client:
        session = RecordingSession([FakeResponse(200, payload=[])], clock=FakeClock())
        client._transport._session = cast(Any, session)
        await client._get("/heroStats")

    assert "Authorization" not in session.sent_headers[0]


# --- Rejected keys ---------------------------------------------------------------

_MALFORMED = '{"error":"Invalid API key format"}'
_UNKNOWN = (
    '{"error":"API key invalid. Please check the API dashboard or email '
    'support@opendota.com."}'
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,reason",
    [
        (_MALFORMED, "Invalid API key format"),
        (
            _UNKNOWN,
            (
                "API key invalid. Please check the API dashboard or email "
                "support@opendota.com."
            ),
        ),
    ],
)
async def test_rejected_key_raises_invalid_api_key_error(body, reason):
    transport, session = make_transport([_text_response(400, body)], api_key=KEY)

    with pytest.raises(InvalidAPIKeyError) as exc_info:
        await transport.request("GET", "/heroStats")

    assert exc_info.value.reason == reason
    assert exc_info.value.status_code == 400
    assert session.calls == 1, "a rejected key can never succeed, so it is not retried"


@pytest.mark.asyncio
async def test_invalid_api_key_error_is_still_an_http_status_error():
    """Existing `except HTTPStatusError` handlers keep catching it."""
    transport, _ = make_transport([_text_response(400, _MALFORMED)], api_key=KEY)

    with pytest.raises(HTTPStatusError):
        await transport.request("GET", "/heroStats")


def test_invalid_api_key_error_message_is_actionable_and_keyless():
    exc = InvalidAPIKeyError(
        reason="Invalid API key format",
        status_code=400,
        method="GET",
        url="https://api.opendota.com/api/heroStats",
    )

    assert str(exc) == (
        "OpenDota rejected the API key (Invalid API key format). Check the `api_key` "
        "argument or the OPENDOTA_API_KEY environment variable, or remove the key to "
        "send requests anonymously."
    )
    assert KEY not in str(exc)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        '{"error":"invalid match_id"}',  # another 400 OpenDota can send
        "Bad Request",  # not JSON
        '["API key"]',  # JSON, but not the {"error": ...} shape
        '{"error": 42}',
    ],
)
async def test_other_400s_stay_plain_http_status_errors(body):
    transport, _ = make_transport([_text_response(400, body)], api_key=KEY)

    with pytest.raises(HTTPStatusError) as exc_info:
        await transport.request("GET", "/x")

    assert type(exc_info.value) is HTTPStatusError


@pytest.mark.asyncio
async def test_key_error_body_without_a_key_sent_is_not_misreported():
    """Only a request that carried a key can have had it rejected."""
    with patch.dict(os.environ, {}, clear=True):
        transport, session = make_transport(
            [_text_response(400, _MALFORMED)], api_key=None
        )

    with pytest.raises(HTTPStatusError) as exc_info:
        await transport.request("GET", "/x")

    assert type(exc_info.value) is HTTPStatusError
    assert "Authorization" not in session.sent_headers[0]


def _text_response(status_code, text):
    response = FakeResponse(status_code)
    response.text = text
    return response
