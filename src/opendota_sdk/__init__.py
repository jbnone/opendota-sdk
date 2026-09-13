"""OpenDota SDK - A modern, domain-driven Python SDK for the OpenDota API."""

from opendota_sdk._config import OpenDotaClientConfig, config_from_env, default_config
from opendota_sdk._errors import (
    HTTPStatusError,
    OpenDotaError,
    RateLimitError,
    ResponseDecodeError,
    TransportError,
)
from opendota_sdk.client import OpenDotaAsyncClient
from opendota_sdk.models import Hero, Item

__version__ = "0.1.0"
__all__ = [
    "HTTPStatusError",
    "Hero",
    "Item",
    "OpenDotaAsyncClient",
    "OpenDotaClientConfig",
    "OpenDotaError",
    "RateLimitError",
    "ResponseDecodeError",
    "TransportError",
    "config_from_env",
    "default_config",
]
