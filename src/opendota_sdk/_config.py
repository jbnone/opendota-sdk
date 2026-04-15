"""Configuration for OpenDota SDK transport and client behavior."""

import os
from dataclasses import dataclass, field


@dataclass
class OpenDotaClientConfig:
    """Configuration for OpenDota API client.

    Attributes:
        api_key: Optional API key for authentication. If not provided, checks
            OPENDOTA_API_KEY environment variable.
        base_url: Base URL for the OpenDota API.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retries for failed requests.
        backoff_factor: Exponential backoff factor for retries.
        retry_on_status: HTTP status codes that trigger automatic retries.
        default_headers: Default headers to include in all requests.
        verify_ssl: Whether to verify SSL certificates.
        trust_env: Whether to trust environment settings for HTTP proxies, etc.
    """

    api_key: str | None = None
    base_url: str = "https://api.opendota.com/api"
    timeout: float = 10.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    retry_on_status: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    default_headers: dict[str, str] = field(
        default_factory=lambda: {"Accept": "application/json"}
    )
    verify_ssl: bool = True
    trust_env: bool = True

    def __post_init__(self) -> None:
        """Populate api_key from environment if not provided."""
        if not self.api_key:
            self.api_key = os.getenv("OPENDOTA_API_KEY")


def default_config() -> OpenDotaClientConfig:
    """Create a default OpenDota client configuration.

    Returns:
        An OpenDotaClientConfig with sensible defaults for the OpenDota API.
    """
    return OpenDotaClientConfig()


def config_from_env() -> OpenDotaClientConfig:
    """Create configuration from environment variables.

    Reads:
        OPENDOTA_API_KEY: API key for authentication.
        OPENDOTA_BASE_URL: Base URL for the API (default: https://api.opendota.com/api).
        OPENDOTA_TIMEOUT: Request timeout in seconds (default: 10.0).
        OPENDOTA_MAX_RETRIES: Maximum number of retries (default: 3).

    Returns:
        An OpenDotaClientConfig populated from environment variables.
    """
    return OpenDotaClientConfig(
        api_key=os.getenv("OPENDOTA_API_KEY"),
        base_url=os.getenv("OPENDOTA_BASE_URL", "https://api.opendota.com/api"),
        timeout=float(os.getenv("OPENDOTA_TIMEOUT", "10.0")),
        max_retries=int(os.getenv("OPENDOTA_MAX_RETRIES", "3")),
    )
