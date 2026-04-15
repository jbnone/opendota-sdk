"""OpenDota SDK - A modern, type-safe Python SDK for the OpenDota API."""

from opendota_sdk._config import OpenDotaClientConfig, config_from_env, default_config
from opendota_sdk._errors import (
    HTTPStatusError,
    OpenDotaError,
    RateLimitError,
    ResponseDecodeError,
    TransportError,
)
from opendota_sdk.client import OpenDotaAsyncClient, OpenDotaClient

__version__ = "0.1.0"
__all__ = [
    "OpenDotaClient",
    "OpenDotaAsyncClient",
    "OpenDotaClientConfig",
    "OpenDotaError",
    "HTTPStatusError",
    "RateLimitError",
    "TransportError",
    "ResponseDecodeError",
    "default_config",
    "config_from_env",
]
