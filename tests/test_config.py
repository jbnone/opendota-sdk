"""Tests for configuration handling."""

import os
import pytest
from unittest.mock import patch

from opendota_sdk._config import OpenDotaClientConfig, config_from_env


def test_default_values():
    """Test that default configuration has expected values."""
    config = OpenDotaClientConfig()

    assert config.api_key is None
    assert config.base_url == "https://api.opendota.com/api"
    assert config.timeout == 10.0
    assert config.max_retries == 3
    assert config.backoff_factor == 0.5
    assert config.retry_on_status == [429, 500, 502, 503, 504]
    assert config.extra_headers == {}
    assert config.verify_ssl is True
    assert config.trust_env is True


def test_custom_values():
    """Test configuration with custom values."""
    config = OpenDotaClientConfig(
        api_key="custom_key",
        base_url="https://custom.com/api",
        timeout=30.0,
        max_retries=5,
        backoff_factor=1.0,
        verify_ssl=False,
        trust_env=False,
    )

    assert config.api_key == "custom_key"
    assert config.base_url == "https://custom.com/api"
    assert config.timeout == 30.0
    assert config.max_retries == 5
    assert config.backoff_factor == 1.0
    assert config.verify_ssl is False
    assert config.trust_env is False


@pytest.mark.parametrize(
    "config1_kwargs,config2_kwargs,expected",
    [
        (
            {"api_key": "key1", "base_url": "https://api1.com", "timeout": 10.0},
            {"api_key": "key2", "base_url": "https://api2.com", "timeout": 20.0},
            {"api_key": "key2", "base_url": "https://api2.com", "timeout": 20.0},
        ),
        (
            {"api_key": "key1", "base_url": "https://api1.com"},
            {"api_key": None, "base_url": ""},
            {"api_key": "key1", "base_url": "https://api1.com"},
        ),
        (
            {"verify_ssl": True, "trust_env": True},
            {"verify_ssl": False, "trust_env": False},
            {"verify_ssl": False, "trust_env": False},
        ),
    ],
)
def test_merge_other(config1_kwargs, config2_kwargs, expected):
    """Test merging configurations."""
    config1 = OpenDotaClientConfig(**config1_kwargs)
    config2 = OpenDotaClientConfig(**config2_kwargs)

    merged = config1.merge_other(config2)

    for key, value in expected.items():
        assert getattr(merged, key) == value


def test_merge_other_extra_headers_combined():
    """Test that extra_headers are combined during merge."""
    config1 = OpenDotaClientConfig(extra_headers={"X-Custom": "value1"})
    config2 = OpenDotaClientConfig(extra_headers={"X-Other": "value2"})

    merged = config1.merge_other(config2)

    assert merged.extra_headers == {"X-Custom": "value1", "X-Other": "value2"}


def test_merge_other_extra_headers_override():
    """Test that extra_headers from second config override first."""
    config1 = OpenDotaClientConfig(extra_headers={"X-Custom": "value1"})
    config2 = OpenDotaClientConfig(extra_headers={"X-Custom": "value2"})

    merged = config1.merge_other(config2)

    assert merged.extra_headers == {"X-Custom": "value2"}


def test_merge_other_boolean_fallback():
    """Test boolean fallback when second config does not specify."""
    config1 = OpenDotaClientConfig(verify_ssl=True)
    config2 = OpenDotaClientConfig()

    merged = config1.merge_other(config2)

    assert merged.verify_ssl is True


@pytest.mark.parametrize(
    "env_vars,expected_attr,expected_value",
    [
        ({"OPENDOTA_API_KEY": "env_key"}, "api_key", "env_key"),
        (
            {"OPENDOTA_BASE_URL": "https://custom.com/api"},
            "base_url",
            "https://custom.com/api",
        ),
        ({"OPENDOTA_TIMEOUT": "30.5"}, "timeout", 30.5),
        ({"OPENDOTA_MAX_RETRIES": "5"}, "max_retries", 5),
    ],
)
def test_config_from_env_reads_values(env_vars, expected_attr, expected_value):
    """Test that environment variables are read correctly."""
    with patch.dict(os.environ, env_vars):
        config = config_from_env()
        assert getattr(config, expected_attr) == expected_value


def test_config_from_env_with_no_env_vars():
    """Test config_from_env falls back to defaults when no environment variables are set."""
    with patch.dict(os.environ, {}, clear=True):
        config = config_from_env()

        assert config.api_key is None
        assert config.base_url == "https://api.opendota.com/api"
        assert config.timeout == 10.0
        assert config.max_retries == 3
