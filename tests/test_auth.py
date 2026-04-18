"""Tests for authentication handler."""

import os
import pytest
from unittest.mock import patch

from opendota_sdk.http._auth import AuthHandler


@pytest.mark.parametrize(
    "api_key,header_name",
    [
        ("my_key", "X-API-Key"),
        ("my_key", "Authorization"),
    ],
)
def test_init_with_api_key(api_key, header_name):
    """Test initialization with an explicit API key."""
    handler = AuthHandler(api_key=api_key, header_name=header_name)
    assert handler.api_key == api_key
    assert handler.header_name == header_name


def test_init_reads_from_env():
    """Test that API key is read from environment if not provided."""
    with patch.dict(os.environ, {"OPENDOTA_API_KEY": "env_key"}):
        handler = AuthHandler()
        assert handler.api_key == "env_key"


def test_init_api_key_takes_precedence_over_env():
    """Test that explicit API key takes precedence over environment variable."""
    with patch.dict(os.environ, {"OPENDOTA_API_KEY": "env_key"}):
        handler = AuthHandler(api_key="explicit_key")
        assert handler.api_key == "explicit_key"


def test_init_no_api_key_no_env():
    """Test initialization with no API key and no environment variable."""
    with patch.dict(os.environ, {}, clear=True):
        handler = AuthHandler()
        assert handler.api_key is None


@pytest.mark.parametrize(
    "api_key,header_name,expected_header",
    [
        ("test_key", "X-API-Key", "X-API-Key"),
        ("test_key", "Authorization", "Authorization"),
    ],
)
def test_apply_to_headers_with_api_key(api_key, header_name, expected_header):
    """Test that API key is injected into headers."""
    handler = AuthHandler(api_key=api_key, header_name=header_name)
    headers = {"Content-Type": "application/json"}
    result = handler.apply_to_headers(headers)

    assert result[expected_header] == api_key
    assert result["Content-Type"] == "application/json"


def test_apply_to_headers_without_api_key():
    """Test that headers are not modified if no API key is set."""
    handler = AuthHandler(api_key=None)
    headers = {"Content-Type": "application/json"}
    result = handler.apply_to_headers(headers)

    assert result == headers
    assert "X-API-Key" not in result


def test_apply_to_headers_does_not_mutate_original():
    """Test that the original headers dict is not mutated."""
    handler = AuthHandler(api_key="test_key")
    headers = {"Content-Type": "application/json"}
    result = handler.apply_to_headers(headers)

    assert "X-API-Key" not in headers
    assert "X-API-Key" in result


@pytest.mark.parametrize(
    "api_key,expected",
    [
        ("test_key", True),
        (None, False),
    ],
)
def test_has_auth(api_key, expected):
    """Test has_auth returns correct value based on API key presence."""
    handler = AuthHandler(api_key=api_key)
    assert handler.has_auth() is expected
