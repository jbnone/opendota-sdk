# Configuration

`OpenDotaAsyncClient` can be configured three ways, in increasing order of control.

## Keyword arguments

```python
client = OpenDotaAsyncClient(
    api_key="...",
    timeout=15.0,
    max_retries=5,
    base_url="https://api.opendota.com/api",
    max_concurrency=10,
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
| `OPENDOTA_MAX_CONCURRENCY` | `10` |

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
    max_concurrency=10,
    max_retry_after=120.0,
)
client = OpenDotaAsyncClient(config=config)
```

Passing `config` takes over entirely — the other `OpenDotaAsyncClient` keyword arguments
are ignored when `config` is given.

## Concurrency and rate limits

`max_concurrency` caps how many requests one client has in flight at once; the rest
queue for a free slot. The default, 10, matches the HTTP connection pool — above it,
extra connections are opened and thrown away instead of reused. It matters as soon as
you fan out with `asyncio.gather`: without it, gathering a per-hero call over every hero
would open well over a hundred connections at once.

The cap bounds a burst; it does not keep you under OpenDota's quota (60 requests a
minute without a key, 300 with one). When that limit is hit, the client waits it out
for you — see [Errors → Rate limits](errors.md#rate-limits). `max_retry_after` (default
120 seconds) is the longest it will wait; a 429 asking for longer is raised immediately
rather than silently stalling your program.

Two configs can be merged, with the second's set values taking precedence:

```python
merged = default_config().merge_other(config_from_env())
```

Full reference: [`OpenDotaClientConfig`][opendota_sdk.OpenDotaClientConfig].
