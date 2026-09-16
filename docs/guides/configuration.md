# Configuration

`OpenDotaAsyncClient` can be configured three ways, in increasing order of control.

## Keyword arguments

```python
client = OpenDotaAsyncClient(
    api_key="...",
    timeout=15.0,
    max_retries=5,
    base_url="https://api.opendota.com/api",
)
```

Covers the common cases. `api_key` falls back to the `OPENDOTA_API_KEY` environment
variable when omitted.

## From the environment

```python
from opendota_sdk import OpenDotaAsyncClient, config_from_env

client = OpenDotaAsyncClient(config=config_from_env())
```

Reads:

| Variable | Default |
|---|---|
| `OPENDOTA_API_KEY` | unset |
| `OPENDOTA_BASE_URL` | `https://api.opendota.com/api` |
| `OPENDOTA_TIMEOUT` | `10.0` |
| `OPENDOTA_MAX_RETRIES` | `3` |

## A full config object

```python
from opendota_sdk import OpenDotaAsyncClient, OpenDotaClientConfig

config = OpenDotaClientConfig(
    api_key="...",
    timeout=15.0,
    max_retries=5,
    backoff_factor=0.5,
    retry_on_status=[429, 500, 502, 503, 504],
    extra_headers={"User-Agent": "my-app/1.0"},
    verify_ssl=True,
    trust_env=True,
)
client = OpenDotaAsyncClient(config=config)
```

Passing `config` takes over entirely — the other `OpenDotaAsyncClient` keyword arguments
are ignored when `config` is given.

Two configs can be merged, with the second's set values taking precedence:

```python
merged = default_config().merge_other(config_from_env())
```

Full reference: [`OpenDotaClientConfig`][opendota_sdk.OpenDotaClientConfig].
