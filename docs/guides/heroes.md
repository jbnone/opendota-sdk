# Heroes

```python
async with OpenDotaAsyncClient() as client:
    heroes = await client.get_heroes()
    am = await client.get_hero(hero_name="npc_dota_hero_antimage")
```

`get_heroes()` merges five OpenDota endpoints — `/heroes`, `/constants/heroes`,
`/constants/hero_abilities`, `/constants/abilities`, and `/constants/hero_lore` — into
typed [`Hero`][opendota_sdk.Hero] models, fetched concurrently and cached per
client the same way [items](items.md) are.

## What you get

```python
am.localized_name  # "Anti-Mage"
am.primary_attribute  # HeroPrimaryAttribute.AGILITY
am.roles  # [HeroRole.CARRY, HeroRole.ESCAPE, ...]
am.abilities  # list[HeroAbility], resolved from /constants/abilities
am.talents  # list[HeroTalent], each with a resolved display title
am.lore  # backstory text
am.innate_abilities  # abilities where is_innate is True — count varies per hero
```

Abilities carry their own tooltip data (`title`, `description`, `behaviors`,
`attributes`, `mana_cost`, `cooldown`) rather than just the bare name references
OpenDota's `hero_abilities` constants use — the SDK resolves those references against
`/constants/abilities` for you.

## Looking up a single hero

```python
hero = await client.get_hero(hero_id=1)
hero = await client.get_hero(hero_name="npc_dota_hero_antimage")
```

Exactly one of `hero_id` / `hero_name` must be given, and a lookup that finds nothing
returns `None` — the same contract as [`get_item()`](items.md#looking-up-a-single-item).

## Hero statistics

Heroes also expose live pick/win data — see [Hero Statistics](hero-stats.md).

Full field reference: [`Hero`][opendota_sdk.Hero],
[`HeroAbility`][opendota_sdk.HeroAbility],
[`HeroTalent`][opendota_sdk.HeroTalent].
