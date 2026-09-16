# Quickstart

## The client

Every SDK call goes through `OpenDotaAsyncClient`. It's async-only — there's no
synchronous variant.

```python
from opendota_sdk import OpenDotaAsyncClient

async with OpenDotaAsyncClient() as client:
    heroes = await client.get_heroes()
```

Entering the client as an async context manager does two things:

1. Sets up the transport used by every `get_*` call.
2. Binds the client as the **active client** for the current context, which is what lets
   model relationship methods like `hero.get_stats()` work without you passing a client
   into them explicitly.

On exit, the client is unbound and its underlying HTTP connections are closed.

## Outside `async with`

Scripts, REPLs, and notebooks that can't hold an `async with` block for their whole
lifetime can bind the client manually:

```python
client = OpenDotaAsyncClient()
client.activate()

heroes = await client.get_heroes()
stats = await heroes[0].get_stats()

client.deactivate()
await client.close()
```

Calling a relationship method with no client active — e.g. `hero.get_stats()` before
`activate()` or outside any `async with` block — raises `OpenDotaError` with a message
telling you how to fix it, rather than failing silently.

## Configuration

```python
from opendota_sdk import OpenDotaAsyncClient, OpenDotaClientConfig, config_from_env

# Keyword arguments
client = OpenDotaAsyncClient(api_key="...", timeout=15.0, max_retries=5)

# From environment variables (OPENDOTA_API_KEY, OPENDOTA_BASE_URL, ...)
client = OpenDotaAsyncClient(config=config_from_env())

# Explicit config object
client = OpenDotaAsyncClient(config=OpenDotaClientConfig(api_key="..."))
```

See [Configuration](guides/configuration.md) for every option.

## Caching

`get_heroes()`, `get_items()`, and `get_hero_stats()` each fetch once per client instance
and cache the typed result. Calling them again — including concurrently via
`asyncio.gather()` — never issues a second request; you always get a fresh copy of the
cached list back, so mutating what you receive never corrupts the cache. Create a new
client if you need to observe fresh data (this matters most for `get_hero_stats()`, which
is live aggregate data rather than patch-gated constants).
