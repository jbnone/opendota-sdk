# OpenDota SDK

An async Python SDK for the [OpenDota API](https://docs.opendota.com/), returning typed
domain objects instead of raw JSON. The SDK handles HTTP, retries, and joining API
responses with [dotaconstants](https://github.com/odota/dotaconstants) data so you don't
have to.

```python
from opendota_sdk import HeroName, OpenDotaAsyncClient

async with OpenDotaAsyncClient() as client:
    heroes = await client.get_heroes()
    items = await client.get_items()

    hero = await client.get_hero(HeroName.ANTI_MAGE)
    stats = await hero.get_stats()
```

## Install

```bash
pip install opendota-sdk
```

Requires Python 3.11+.

## What's covered today

The SDK is still alpha and grows one domain slice at a time. Today it covers:

- **Items** — [`get_items()`](api/client.md) / `get_item()`, returning typed `Item`
  models assembled from `/constants/items`.
- **Heroes** — [`get_heroes()`](api/client.md) / `get_hero()`, merging `/heroes` with
  four constants endpoints into typed `Hero` models with abilities, talents, and lore.
- **Hero statistics** — [`get_hero_stats()`](api/client.md) / `get_hero_stat()`,
  plus the `hero.get_stats()` relationship method, exposing live pick/win data.

Player and match domains, and a broader relationship-navigation layer, aren't built yet.
See the project's `AGENTS.md` for the full picture of what's current versus planned.

## Where to go next

- [Quickstart](quickstart.md) for the client lifecycle (`async with`, `activate()`).
- The [API reference](api/client.md) for full signatures, generated from the source docstrings.
