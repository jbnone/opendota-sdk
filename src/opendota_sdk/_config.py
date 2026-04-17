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
        extra_headers: Extra headers to include in all requests.
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
    extra_headers: dict[str, str] = field(default_factory=dict)
    verify_ssl: bool = True
    trust_env: bool = True

    def merge_other(self, other: "OpenDotaClientConfig") -> "OpenDotaClientConfig":
        """Merge another config into this one, with the other config taking precedence."""
        return OpenDotaClientConfig(
            api_key=other.api_key or self.api_key,
            base_url=other.base_url or self.base_url,
            timeout=other.timeout or self.timeout,
            max_retries=other.max_retries or self.max_retries,
            backoff_factor=other.backoff_factor or self.backoff_factor,
            retry_on_status=other.retry_on_status or self.retry_on_status,
            extra_headers={**self.extra_headers, **other.extra_headers},
            verify_ssl=other.verify_ssl
            if other.verify_ssl is not None
            else self.verify_ssl,
            trust_env=other.trust_env
            if other.trust_env is not None
            else self.trust_env,
        )


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
