# OpenDota SDK — Agent Instructions

**Status**: Alpha, architecture still settling  
**Current focus**: Async client foundation, item domain vertical slice, hero model flow  
**Design direction**: Domain-focused SDK with transparent constant enrichment

---

## 1. Purpose

The OpenDota API exposes useful data, but the raw responses are not ergonomic. The SDK exists to:

- expose typed Python objects instead of unstructured payloads
- hide constant-enrichment details behind the SDK surface
- keep HTTP, retry, auth, and normalization concerns internal
- grow toward richer domain objects without locking the project into premature abstractions

The project is **not** a thin endpoint wrapper, but it is also **not yet** the fully realized service-and-session architecture described in earlier drafts. Contributions should follow the code that exists today and extend it incrementally.

---

## 2. Current Architectural Reality

### 2.1 Public Entry Point

The current user-facing entry point is `OpenDotaAsyncClient`.

```python
from opendota_sdk import OpenDotaAsyncClient

async with OpenDotaAsyncClient() as client:
    heroes = await client.get_heroes()
    items = await client.get_items()
```

Rules:

- The SDK is **async-only**.
- Do **not** add or reintroduce a synchronous client.
- Do **not** instruct contributors to build around a `Session` class unless that work explicitly introduces it.

### 2.2 Current Domain Coverage

Implemented today:

- item constants flow via `get_items()`
- hero list flow via `get_heroes()` returning typed `Hero` models
- typed `Item` and `Hero` models
- internal transport, auth, retry, and error layers

Planned but not implemented yet:

- player domain objects
- match domain objects
- service-per-resource architecture
- session container abstraction
- generalized relationship navigation

When writing code or instructions, be explicit about whether something is **current** or **target architecture**.

### 2.3 Constants Handling

Constants are an internal implementation detail, not public API.

- there is no dedicated constants-registry module — a past `ConstantsRegistry` class (in
  `src/opendota_sdk/constants.py`) was removed once it became a redundant cache: `client.get_items()`
  already guards its own fetch behind a cache+lock, so the registry's internal raw-payload cache never
  got exercised a second time in practice, with no other consumer anywhere in the codebase
- `OpenDotaAsyncClient.get_items()` fetches `/constants/items` directly via `self._get(...)`, exactly
  like `get_heroes()` fetches its five raw payloads — no intermediate raw-cache class for either domain
- contributors should avoid designing user workflows around raw constants access; `get_items()`/
  `get_item()` are the supported path

`OpenDotaAsyncClient.get_items()`/`get_item()` cache the **assembled, indexed** `Item` result on the
client itself — the same shape heroes use (see §6) — behind an `asyncio.Lock` that guards against two
concurrent calls both triggering a fetch before either populates the cache. Both `get_items()` and
`get_heroes()` return a fresh copy of the cached list on every call, so mutating a returned list never
corrupts the cache; the objects inside are frozen dataclasses, so sharing references to them across calls
is safe.

---

## 3. Design Principles

### 3.1 Domain-First Surface

Prefer typed models and meaningful names over raw response plumbing.

Wrong:

```python
payload["item_id"]
payload["hero_id"]
```

Better:

```python
item.name
hero.localized_name
```

This principle is strongest today in the item flow and should guide future work.

### 3.2 Async All The Way

- HTTP access is always async
- client entry points are always async
- do not add sync mirrors for convenience

If a future domain object needs network access, that method should be async.

### 3.3 Internal Enrichment

The SDK should absorb enrichment logic so callers do not manually join API payloads with dotaconstants.

Current examples:

- `OpenDotaAsyncClient.get_items()` returns typed `Item` objects assembled from constants payloads
- `OpenDotaAsyncClient.get_heroes()` merges `/heroes` with `/constants/heroes` and returns typed `Hero` models

### 3.4 Incremental Generalization

Do not build a large abstraction framework ahead of usage.

Current rule of thumb:

- if the behavior only exists for items, keep it item-scoped
- if the pattern has already repeated and the abstraction is obvious, generalize it

The repo is still shaping its stable architecture. Prefer a working vertical slice over speculative infrastructure.

### 3.5 Small Public API

Keep `src/opendota_sdk/__init__.py` minimal.

Public exports should be limited to stable, user-facing types such as:

- `OpenDotaAsyncClient`
- `OpenDotaClientConfig`
- SDK error types
- selected user-facing models like `Item`

Avoid exporting internal helpers, registries, transport classes, or normalization machinery.

---

## 4. Current Module Map

```text
src/opendota_sdk/
├── __init__.py          # Public exports only
├── _config.py           # Client and transport configuration
├── _errors.py           # SDK-specific exception types
├── _records.py          # Raw item record boundary before assembly
├── assembler.py         # Item normalization and assembly
├── client.py            # OpenDotaAsyncClient (owns all raw fetching and caching)
├── enums.py             # Hero-related enums and shared enum types
├── models.py            # Typed Item and Hero models, plus item enums
└── http/
    ├── _auth.py         # Header-based auth handling
    ├── _retry.py        # Retry policy and decorator builder
    └── _transport.py    # Sync/async transport implementations
```

Notes:

- There is no `resources/` directory. A past `AsyncResourceBase` scaffold there was removed for having
  zero consumers and zero tests since the day it was added — see §11. Do not assume `PlayerService`,
  `HeroService`, `BaseService`, or any resource/service module exists.
- `models.py` currently contains public-facing dataclasses and item enums despite its generic name.

---

## 5. Item Slice Is The Reference Pattern

The item flow is the current proof of concept for the broader SDK direction.

### 5.1 Current Item Pipeline

```text
OpenDota constants route
    -> OpenDotaAsyncClient.get_items() (raw fetch + cache)
    -> ItemRecord
    -> Assembler
    -> Item
```

### 5.2 What To Preserve

- a clear boundary between raw payloads and typed models
- normalization in one owning place
- typed enums for item-specific classifications
- user-facing return values that are richer than raw dictionaries

### 5.3 What Not To Do

- do not expose the constants registry as the recommended user path
- do not bypass the assembler when constructing public `Item` objects from API data
- do not spread item normalization rules across unrelated files

### 5.4 Extending Items

When improving item behavior:

- start at `assembler.py`, `_records.py`, `models.py`, or `client.py`
- preserve the raw-record -> assembler -> model flow
- add focused tests before widening scope

---

## 6. Hero Flow Guidance

Heroes currently follow a lighter path than items, but it is no longer a bare pass-through.

Current shape:

- `OpenDotaAsyncClient.get_heroes()` fetches `/heroes`, `/constants/heroes`, `/constants/hero_abilities`,
  `/constants/abilities`, and `/constants/hero_lore` concurrently (`asyncio.gather`)
- the merged result is cached on the client instance (`self._heroes_cache`, plus `_heroes_by_id`/
  `_heroes_by_name` indices for O(1) `get_hero()` lookup), guarded by `self._heroes_lock` against two
  concurrent calls both triggering a fetch — the same shape `get_items()`/`get_item()` use (§2.3);
  repeated calls do not re-fetch and each call returns a fresh copy of the cached list
- `OpenDotaAsyncClient._make_heroes()` (a private static method — no mixin) merges the five payloads per hero: base stats by numeric id
  (`/heroes` + `/constants/heroes`), ability/talent name references by hero internal name
  (`/constants/hero_abilities`), which are then resolved against `/constants/abilities` by ability name
  (also used to resolve talent titles — talent names are themselves ability-shaped entries), and lore by
  the hero's short name (`/constants/hero_lore` keys drop the `npc_dota_hero_` prefix)
- each merged payload is passed to `Assembler.normalize_hero()`, which reuses the same generic
  normalization helpers items rely on (`_normalize_enum`, `_normalize_enum_list`, `_normalize_int`,
  `_normalize_float`, `_normalize_bool`, etc.) to coerce `primary_attr`/`attack_type`/`roles` into real
  enum members, default missing optional fields safely, and raise `OpenDotaError` if `id`, `name`,
  `localized_name`, `primary_attr`, or `attack_type` can't be resolved from the payload
- `Hero` carries `abilities: list[HeroAbility]`, `talents: list[HeroTalent]` (each with a resolved
  `title`), `lore: str`, a computed `innate_abilities` property (filters `abilities` by `is_innate` —
  cardinality varies per hero, not always exactly one), and a `raw` field (mirroring `Item.raw`) with
  the full merged payload

Implications:

- hero enrichment logic still lives closer to the client than the item flow does (no `HeroRecord`
  intermediate dataclass — the merged dict is normalized directly), but it no longer does
  `Hero(**merged_dict)`; it goes through the assembler like items do
- `Assembler` is shared between the item and hero flows: composite methods (`normalize_item`,
  `normalize_hero`, `normalize_hero_ability`, `normalize_hero_talent`) and their field-specific helpers
  stay flow-specific, but generic scalar/enum coercion helpers are reused across both — extend those
  shared helpers rather than duplicating them if a third domain needs the same kind of coercion
- `HeroAbility` reuses `Attribute` (renamed from `ItemAttribute` — no longer item-only) and
  `AbilityBehavior` (renamed from `ItemBehavior`) from the item slice, since `/constants/abilities`
  shares real schema with `items.json`'s own `attrib`/`behavior` fields — confirmed by direct data
  comparison, not assumed. `Item.abilities` (`ItemAbility`/`ItemAbilityType`) is unrelated and was NOT
  reused: it's a small self-contained nested field, structurally nothing like a hero's ability-name
  references into a separate lookup file
- do not force heroes into the item architecture mechanically (no `HeroRecord`, no hero-specific
  assembler subclass) unless real duplication emerges beyond what the shared helpers already cover
- `HeroAbility.mana_cost`/`cooldown` are `list[float]` (via `Assembler._normalize_float_list`), not
  `Item`'s `bool | int` convention — confirmed via direct data comparison that ability `mc`/`cd` are
  always numeric strings or per-level lists, never booleans, so forcing them into Item's scalar
  convention would misrepresent the data. Empty list means no cost/cooldown; length > 1 means it scales
  by ability level; unparseable entries (~0.1% of real data, e.g. `"undefined"`) are skipped, not raised

---

## 7. Future Architecture Direction

The long-term direction may still include a session container and resource services, but those are **future moves**, not assumptions contributors should code against today.

If future work introduces:

- `Session`
- `PlayerService`
- `MatchService`
- `HeroService`
- domain objects that own async relationship methods

then that work should be introduced deliberately, with tests and updated docs, rather than implied by the instructions file alone.

Until then:

- prefer `OpenDotaAsyncClient` over `Session`
- prefer concrete implemented flows over imagined service boundaries
- avoid scaffolding placeholder modules just to satisfy an architectural sketch

---

## 8. Error Handling

Use the existing SDK error hierarchy in `src/opendota_sdk/_errors.py`.

Current error types include:

- `OpenDotaError`
- `TransportError`
- `HTTPStatusError`
- `RateLimitError`
- `ResponseDecodeError`

Guidelines:

- fail with context
- preserve original exceptions with `from exc` when wrapping
- prefer typed SDK exceptions over generic `Exception`
- do not silently swallow malformed data or HTTP failures

---

## 9. Testing Strategy

### 9.1 Current Test Reality

The repo currently uses a flat test layout under `tests/`.

Existing coverage includes:

- config behavior
- auth behavior
- retry behavior
- transport behavior
- item assembly
- item constants registry behavior
- async client behavior

Do not rewrite the test structure preemptively unless there is a clear payoff.

### 9.2 Testing Expectations For New Work

For changes in the item or hero flow, prefer focused tests near the current pattern:

- raw record parsing tests
- assembler normalization tests
- constants registry tests
- client-level async behavior tests

If future player or match domains are added, test the vertical slice that actually exists rather than only internal helpers.

### 9.3 Validation Commands

Use the existing toolchain:

```bash
uv run pytest
uv run ruff check
uv run ty check
```

For narrower work, run the smallest relevant subset first.

Always run `ruff check` and `ty check` on any file you touch and resolve issues before considering the work done, not just `pytest`. Pre-existing issues in files you did not touch may be left alone but should be called out rather than silently ignored.

---

## 10. Contribution Rules

### 10.1 Before Adding Architecture

Ask:

1. Does the abstraction correspond to behavior that already exists in at least one concrete flow?
2. Will this make the next domain entity easier to implement, or only make the design look cleaner on paper?
3. Can the same goal be reached with a smaller, local change?

### 10.2 Public API Discipline

- keep internal machinery private by default
- avoid adding new exports casually
- avoid exposing raw constants access unless there is a strong user-facing reason
- prefer async client methods over standalone fetch helpers

### 10.3 Model Design

- use dataclasses for typed domain data
- keep value-like models predictable
- if a model is meant to represent static game data, consider immutability deliberately, but do not change mutability casually without checking current usage
- `Item`, `Hero`, `ItemAbility`, `HeroAbility`, `HeroTalent`, and `Attribute` are all `frozen=True` — a
  deliberate decision (nothing in the codebase mutated a constructed instance, verified before freezing).
  Note this only blocks reassigning a field; it does not make nested `list`/`dict` fields (e.g. `raw`,
  `abilities`) immutable, and `hash()` on these models will raise since they hold unhashable list fields.

### 10.4 Documentation Discipline

When the architecture changes, update:

- `AGENTS.md`
- public examples in `README.md` if affected
- tests that encode the intended usage

The instructions file must describe the current repo shape first and the future direction second.

---

## 11. Anti-Drift Rules

When editing this project, do not introduce instruction drift in these areas:

- do not document `Session` as current API unless it exists in code
- do not document sync clients as supported
- do not describe a `resources/` service layer as implemented, or scaffold one back in, without a
  concrete need — the `AsyncResourceBase` stub that lived there was removed for having zero consumers
  and zero tests since it was first added; a future resource layer should be designed against a real
  domain's actual usage, not resurrected from that shape
- do not reintroduce a `ConstantsRegistry`/`constants.py`-style raw-cache layer without a concrete
  need — it was removed for being a redundant cache with no consumer beyond the client itself
- do not claim player or match domain objects exist until they do
- do not move examples ahead of implementation reality

If the implementation changes materially, update this file in the same work.

---

## 12. Near-Term Priorities

1. Keep the async client stable as the public entry point.
2. Continue polishing the item domain slice as the reference architecture.
3. Improve the hero flow without prematurely forcing a generalized service layer.
4. Introduce new domain entities only when their owning fetch, enrichment, and model path is clear.

---

## 13. References

- [OpenDota API Docs](https://docs.opendota.com/)
- [dotaconstants Repository](https://github.com/odota/dotaconstants)
- [Python AsyncIO Best Practices](https://docs.python.org/3/library/asyncio.html)
