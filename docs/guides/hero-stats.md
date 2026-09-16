# Hero Statistics

`/heroStats` is OpenDota's live aggregate pick/win endpoint. The SDK exposes it two ways:
a bulk client method, and a relationship method on `Hero` itself.

## From the client

```python
async with OpenDotaAsyncClient() as client:
    all_stats = await client.get_hero_stats()
    am_stats = await client.get_hero_stat(hero_id=1)
```

Same shape as [`get_items()`](items.md) / [`get_item()`](heroes.md): one cached,
single-flighted fetch, with `get_hero_stat()` resolving from an index built off it.

## From a hero

```python
hero = await client.get_hero(hero_name="npc_dota_hero_antimage")
stats = await hero.get_stats()
```

`Hero.get_stats()` is a **relationship method** — it resolves the client from whichever
one is currently active (see [Quickstart](../quickstart.md#the-client)) and delegates to
`client.get_hero_stat(hero_id=hero.id)`. It's a one-line convenience, not a second
implementation: it shares the same cache as calling `get_hero_stats()` directly, so
fetching every hero's stats this way still costs one request:

```python
import asyncio

async with OpenDotaAsyncClient() as client:
    heroes = await client.get_heroes()
    stats = await asyncio.gather(*(hero.get_stats() for hero in heroes))
```

Calling `get_stats()` with no client active (outside `async with` / `activate()`) raises
`OpenDotaError`.

## What you get

```python
stats.pub_win_rate  # float | None — None when pub_picks is 0
stats.pro_pick, stats.pro_win, stats.pro_ban
stats.brackets  # list[HeroBracketStats], one per HeroSkillBracket
```

Each entry in `brackets` covers one skill bracket (Herald through Immortal) and has its
own `win_rate` property. `HeroSkillBracket.IMMORTAL`'s counts are always zero — OpenDota
withholds that bracket publicly — but the entry is still present because the underlying
key genuinely exists in the payload.

Fields duplicated from `/constants/heroes` (base stats, name, etc.) are **not** repeated
here — they already live on [`Hero`](heroes.md), which is where you should read them from.

Full field reference: [`HeroStats`][opendota_sdk.HeroStats],
[`HeroBracketStats`][opendota_sdk.HeroBracketStats],
[`HeroSkillBracket`][opendota_sdk.HeroSkillBracket].
