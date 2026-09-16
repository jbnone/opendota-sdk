# Items

```python
async with OpenDotaAsyncClient() as client:
    items = await client.get_items()
    blink = await client.get_item(item_name="blink")
```

`get_items()` fetches `/constants/items` once per client and returns every item as a
typed [`Item`][opendota_sdk.Item] — no manual joining against dotaconstants, and
no raw dictionaries to index into by hand.

## What you get

Instead of raw payload keys:

```python
payload["mc"]  # ???
payload["dname"]  # ???
```

`Item` gives you named, typed fields:

```python
item.mana_cost  # bool | int — False means the item has no mana cost
item.descriptive_name  # "Blink Dagger"
item.cost  # gold cost
item.attributes  # list[Attribute] — tooltip stats
item.abilities  # list[ItemAbility] — effects the item grants
```

Several fields use a `bool | int` (or `bool | list[...]`) shape rather than always being
numeric: `mana_cost`, `health_cost`, `cooldown`, `charges`, and `behaviors` are all
`False` when the item simply doesn't have that property, matching how OpenDota's own
constants represent "not applicable."

## Looking up a single item

```python
item = await client.get_item(item_id=1)
item = await client.get_item(item_name="blink")
```

Exactly one of `item_id` / `item_name` must be given; passing both or neither raises
`ValueError`. A lookup that finds nothing returns `None` rather than raising.

## Caching

The first `get_items()` call fetches and assembles every item; later calls — including
`get_item()`, which calls `get_items()` internally to populate its lookup indices —
return the cached result. See [Caching](../quickstart.md#caching) for the concurrency
guarantee this gives you.

Full field reference: [`Item`][opendota_sdk.Item].
