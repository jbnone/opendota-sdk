# Hero Item Popularity

What a hero tends to buy at each stage of a game, from
`/heroes/{hero_id}/itemPopularity`. The SDK resolves every item id in that response
into a full [`Item`][opendota_sdk.Item], so you get names, costs, and stats rather than
bare numbers.

## From a hero

```python
async with OpenDotaAsyncClient() as client:
    am = await client.get_hero(hero_name="npc_dota_hero_antimage")
    popularity = await am.get_item_popularity()

    for entry in popularity.mid_game[:3]:
        print(entry.item.descriptive_name, entry.purchases)
```

```text
Broadsword 125
Blade of Alacrity 104
Battle Fury 95
```

`Hero.get_item_popularity()` is a relationship method, like
[`Hero.get_stats()`](hero-stats.md): it uses whichever client is active and delegates to
`client.get_hero_item_popularity(hero_id=hero.id)`.

## From the client

```python
popularity = await client.get_hero_item_popularity(hero_id=1)
```

This takes an **id only**. `get_hero()` and `get_hero_stat()` can look a name up for free
in data they already hold; here, resolving a name would mean fetching every hero first.
If you have a name, call `get_hero(hero_name=...)` and then `get_item_popularity()`.

## What the numbers mean

OpenDota takes the hero's **100 most recently parsed matches** and counts every purchase,
sorted into four phases by game time — keeping only items above a cost floor for each
phase:

| Field | Game time | Item cost |
|---|---|---|
| `start_game` | at or before 0:00 | 600 gold or less |
| `early_game` | 0:00 to 10:00 | at least 500 |
| `mid_game` | 10:00 to 25:00 | at least 1,000 |
| `late_game` | 25:00 onwards | at least 2,000 |

Each phase is a list of [`PopularItem`][opendota_sdk.PopularItem] entries — an `item` and
its `purchases` — sorted most-purchased first. `purchases` counts purchases, not
matches: an item bought twice in one match counts twice, so a number can exceed 100.

OpenDota's documentation says this data comes from professional games. Its query
actually samples any parsed match, so treat it as "what players recently built", not
"what pros build".

## Unknown heroes

OpenDota answers an unknown hero id the same way as a hero with no parsed matches: an
empty result, not an error. Check `popularity.is_empty`.

## Caching

Each hero's result is cached on the client after the first fetch, and the item constants
it is resolved against are fetched at most once per client. Two concurrent calls for the
same hero share one request; calls for different heroes run in parallel:

```python
import asyncio

heroes = await client.get_heroes()
# One request per hero, several in flight at once -- not one request in total.
everything = await asyncio.gather(*(hero.get_item_popularity() for hero in heroes))
```

That is a request per hero, so a sweep like this over every hero will reach OpenDota's
rate limit without an API key; the client waits it out for you (see
[Errors → Rate limits](errors.md#rate-limits)). Create a new client to fetch fresh data.

Full reference: [`HeroItemPopularity`][opendota_sdk.HeroItemPopularity],
[`PopularItem`][opendota_sdk.PopularItem].
