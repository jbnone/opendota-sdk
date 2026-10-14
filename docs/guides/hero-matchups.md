# Hero Matchups

How a hero fares against every opposing hero, from `/heroes/{hero_id}/matchups`. The SDK
resolves every opposing hero id into a full [`Hero`][opendota_sdk.Hero], so you get
names and roles rather than bare numbers.

## From a hero

```python
async with OpenDotaAsyncClient() as client:
    am = await client.get_hero(hero_name="npc_dota_hero_antimage")
    result = await am.get_matchups()

    for matchup in result.matchups[:3]:
        print(matchup.hero.localized_name, matchup.games_played, matchup.win_rate)
```

`Hero.get_matchups()` is a relationship method, like
[`Hero.get_stats()`](hero-stats.md): it uses whichever client is active and delegates to
`client.get_hero_matchups(hero_id=hero.id)`.

## From the client

```python
result = await client.get_hero_matchups(hero_id=1)
```

This takes an **id only**, for the same reason as
[item popularity](hero-item-popularity.md): resolving a name would mean fetching every
hero first. If you have a name, call `get_hero(hero_name=...)` and then `get_matchups()`.

## What the numbers mean

The data is **professional-league matches only**. OpenDota's matchups query reads its
Postgres `matches` table, which only receives matches from premium and professional-tier
leagues; public matches are never stored there. The query counts those that started
within the **last year** and pairs the hero with each of the five heroes on the other
team. One match therefore adds one game to each of five matchups.

Each [`HeroMatchup`][opendota_sdk.HeroMatchup] has the opposing `hero`, `games_played`
against it, and `wins` — the matches the queried hero's team won. `win_rate` is
`wins / games_played`, or `None` when there are no games. Entries are sorted most games
first, ties by the opposing hero's name.

OpenDota's documentation does not say which matches are sampled; this is what its query
does.

## Unknown heroes

OpenDota answers an unknown hero id with an empty list, not an error. Check
`result.is_empty`. Opposing hero ids missing from the hero constants (possible mid-patch)
are left out of `matchups`, reported in one warning, and kept on `result.raw`.

## Caching

Each hero's result is cached on the client after the first fetch, and the hero constants
it is resolved against are fetched at most once per client. Two concurrent calls for the
same hero share one request; calls for different heroes run in parallel, one request per
hero, so a sweep over every hero will reach OpenDota's rate limit without an API key; the
client waits it out for you (see [Errors → Rate limits](errors.md#rate-limits)).

Full reference: [`HeroMatchups`][opendota_sdk.HeroMatchups],
[`HeroMatchup`][opendota_sdk.HeroMatchup].
