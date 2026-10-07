"""Tests for authentication handler.

OpenDota reads the API key only from `Authorization: Bearer <key>` (or `?api_key=`); any
other header is silently ignored. These tests pin the exact header and value, because the
SDK once sent `X-API-Key` and every keyed user was quietly served as anonymous.
"""

import os
from typing import Any, cast
from unittest.mock import patch

import pytest

from opendota_sdk import OpenDotaAsyncClient
from opendota_sdk.http._auth import AuthHandler
from tests._transport_harness import FakeClock, FakeResponse, RecordingSession

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
