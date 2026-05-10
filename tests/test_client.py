"""Tests for OpenDota client."""

import pytest
from unittest.mock import MagicMock, patch

from opendota_sdk.client import OpenDotaAsyncClient
from opendota_sdk._config import OpenDotaClientConfig


@pytest.mark.asyncio
@patch("opendota_sdk.client.AsyncHTTPTransport")
async def test_async_client_initialization(mock_transport_class):
    """Test async client initialization with config propagation."""
    mock_transport = MagicMock()
    mock_transport_class.return_value = mock_transport

    config = OpenDotaClientConfig(api_key="custom_key")
    client = OpenDotaAsyncClient(config=config)

    assert client._config.api_key == "custom_key"
    mock_transport_class.assert_called_once()


@pytest.mark.asyncio
@patch("opendota_sdk.client.AsyncHTTPTransport")
async def test_async_client_context_manager(mock_transport_class):
    """Test async client as context manager."""
    mock_transport = MagicMock()
    mock_transport_class.return_value = mock_transport

    async def async_close():
        pass

    mock_transport.close = async_close

    async with OpenDotaAsyncClient() as client:
        assert client is not None


@pytest.mark.asyncio
@patch("opendota_sdk.client.AsyncHTTPTransport")
async def test_async_close(mock_transport_class):
    """Test async client close method."""
    mock_transport = MagicMock()
    mock_transport_class.return_value = mock_transport

    async def async_close():
        pass

    mock_transport.close = async_close

    client = OpenDotaAsyncClient()
    await client.close()
