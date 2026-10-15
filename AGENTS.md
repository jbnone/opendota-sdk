# OpenDota SDK — Agent Instructions

**Status**: Alpha, architecture still settling  
**Current focus**: Async client foundation, item domain vertical slice, hero flow and its per-hero endpoints  
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

    hero = await client.get_hero(hero_name="npc_dota_hero_antimage")
    stats = await hero.get_stats()  # relationship method, see §6.2
```

Rules:

- The SDK is **async-only**.
- Do **not** add or reintroduce a synchronous client.
- Do **not** instruct contributors to build around a `Session` class unless that work explicitly introduces it.
- Entering the client as an async context manager also binds it as the **active client** for model
  relationship methods (§6.2). `client.activate()`/`client.deactivate()` do the same outside
  `async with`, for scripts and notebooks.

### 2.2 Current Domain Coverage

Implemented today:

- item constants flow via `get_items()`
- hero list flow via `get_heroes()` returning typed `Hero` models
- hero statistics flow via `get_hero_stats()`/`get_hero_stat()` returning typed `HeroStats` models
- hero item popularity via `get_hero_item_popularity()` returning `HeroItemPopularity`, with every
  item id resolved to an `Item` — the first cross-domain join, and the first per-key endpoint (§6.3)
- hero matchups via `get_hero_matchups()` returning `HeroMatchups`, with every opposing hero id
  resolved to a `Hero` — the second cross-domain join and the second per-key endpoint (§6.4)
- three relationship methods, `Hero.get_stats()`, `Hero.get_item_popularity()`, and
  `Hero.get_matchups()`, resolved through an ambient client (§6.2)
- typed `Item`, `Hero`, `HeroStats`, `HeroItemPopularity`, and `HeroMatchups` models
- internal transport, auth, retry, and error layers, including a per-client concurrency cap and
  rate-limit handling that waits out OpenDota's per-minute window (§8.2)
- standard-library logging under the `opendota_sdk` logger: per-attempt and cache-fill detail at
  DEBUG, retries and rate-limit pauses at INFO, data problems at WARNING (§10.6)

Planned but not implemented yet:

- player domain objects
- match domain objects
- service-per-resource architecture
- session container abstraction
- relationship navigation beyond the three hand-written `Hero` methods — no descriptor, query,
  or resource-graph machinery exists, and none should be added speculatively (§6.2, §11)

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

`get_hero_stats()`/`get_hero_stat()` use that identical cache+lock+index shape even though `/heroStats`
is live aggregate data rather than patch-gated constants. That is deliberate: the lock **is** the
single-flight mechanism, so `asyncio.gather(*(hero.get_stats() for hero in heroes))` over every hero
collapses to one HTTP request instead of one per hero. Dropping the cache to keep the numbers fresh
would silently turn that into N requests. If staleness ever matters, add an explicit refresh or TTL —
do not simply remove the cache.

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

Domain objects that need network access expose it as an async method — `Hero.get_stats()`,
`Hero.get_item_popularity()`, and `Hero.get_matchups()` are the three instances today (§6.2–§6.4).

### 3.3 Internal Enrichment

The SDK should absorb enrichment logic so callers do not manually join API payloads with dotaconstants.

Current examples:

- `OpenDotaAsyncClient.get_items()` returns typed `Item` objects assembled from constants payloads
- `OpenDotaAsyncClient.get_heroes()` merges `/heroes` with `/constants/heroes` and returns typed `Hero` models
- `OpenDotaAsyncClient.get_hero_stats()` folds `/heroStats`'s flat `{bracket}_pick`/`{bracket}_win` keys
  into typed `HeroBracketStats` entries and derives win rates, instead of exposing the raw numeric keys
- `OpenDotaAsyncClient.get_hero_item_popularity()` turns `/heroes/{id}/itemPopularity`'s bare item ids
  into full `Item` objects, joining two domains so the caller never cross-references
  `/constants/items` by hand
- `OpenDotaAsyncClient.get_hero_matchups()` turns `/heroes/{id}/matchups`'s bare opposing hero ids
  into full `Hero` objects, joining the matchups payload with the hero constants

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
- selected user-facing models like `Item`, `Hero`, `HeroStats`, `HeroItemPopularity` (with its
  `PopularItem` entries), and `HeroMatchups` (with its `HeroMatchup` entries), plus the enums they expose
  (`HeroSkillBracket` is exported because `HeroBracketStats.bracket` hands it to callers)

The ambient-client helpers in `_context.py` are **not** exported: `active_client()`, `bind_client()`,
and `unbind_client()` are internal. Users reach them through `async with client` or
`client.activate()`.

Avoid exporting internal helpers, registries, transport classes, or normalization machinery.

### 3.6 Domain Entry Points

When an endpoint is about one entity the SDK already models, its public entry point is a method
on that model, not on the client: `Hero.get_durations()`, not
`OpenDotaAsyncClient.get_hero_durations()`. The client still owns the fetch, the cache, and the
normalization (§6.2), but in a **private** method (`_get_hero_durations()`) that the model method
delegates to through the ambient client. This keeps the public surface domain-shaped (§3.1) and
small (§3.5) without moving any logic into models.

- methods with no single entity to hang on stay public on the client: the collections
  (`get_heroes()`, `get_items()`, `get_hero_stats()`) and the lookups that produce an entity
  (`get_hero()`, `get_item()`)
- the cost is accepted: a caller holding only a hero id calls `get_hero(hero_id=...)` first,
  which fetches the hero constants once per client and caches them
- `get_hero_stat()`, `get_hero_item_popularity()`, and `get_hero_matchups()` predate this rule
  and are public today. Removing the first two would break released callers.
  `get_hero_matchups()` was merged after 0.1.0a10, so making it private before the next
  release breaks nobody; that is the owner's call

---

## 4. Current Module Map

```text
src/opendota_sdk/
├── __init__.py          # Public exports only
├── _config.py           # Client and transport configuration
├── _context.py          # Ambient active-client binding for model relationship methods
├── _errors.py           # SDK-specific exception types
├── _records.py          # Raw item record boundary before assembly
├── assembler.py         # Item, hero, hero-stats, item-popularity, and matchups normalization
├── client.py            # OpenDotaAsyncClient (owns all raw fetching and caching)
├── enums.py             # Hero-related enums and shared enum types
├── models.py            # Typed Item, Hero, HeroStats, HeroItemPopularity, HeroMatchups models, item enums
├── py.typed             # PEP 561 marker; the package ships as typed
└── http/
    ├── _auth.py         # API key as `Authorization: Bearer`, the only header OpenDota reads
    ├── _retry.py        # Retry policy and decorator builder
    └── _transport.py    # Async HTTP transport over niquests (no sync transport)
```

Notes:

- There is no `resources/` directory. A past `AsyncResourceBase` scaffold there was removed for having
  zero consumers and zero tests since the day it was added — see §11. Do not assume `PlayerService`,
  `HeroService`, `BaseService`, or any resource/service module exists.
- `models.py` currently contains public-facing dataclasses and item enums despite its generic name.
- `_context.py` holds only the `ContextVar` machinery. It imports `OpenDotaAsyncClient` solely under
  `TYPE_CHECKING`, which is what keeps `models.py` → `_context.py` and `client.py` → `models.py` free
  of an import cycle. Preserve that when editing it.

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

### 6.1 Hero Model Flow

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

### 6.2 Hero Statistics And Relationship Navigation

`/heroStats` returns live aggregate pick/win data. It repeats every `/constants/heroes` stat field —
those duplicates are **discarded** during normalization, since `Hero` already owns them — and adds the
parts that are actually new:

- flat per-bracket keys `1_pick`/`1_win` … `8_pick`/`8_win`, folded by `Assembler._normalize_brackets()`
  into `list[HeroBracketStats]` keyed by the `HeroSkillBracket` IntEnum (Herald=1 … Immortal=8).
  Bracket 8 is present in the payload but **always zero** — OpenDota withholds Immortal data publicly.
  It is kept rather than dropped because the key genuinely exists; `win_rate` returns `None` when
  `picks == 0`.
- `pub_*`/`turbo_*` totals plus 7-element per-day trend arrays, and `pro_pick`/`pro_win`/`pro_ban`
- computed `win_rate` properties on `HeroBracketStats` and `HeroStats` (`pub_`/`turbo_`/`pro_`), all
  `None` when the matching pick count is zero

`Hero.get_stats()` was the SDK's first relationship method; `Hero.get_item_popularity()` (§6.3) is
the second and `Hero.get_matchups()` (§6.4) the third, built the same way. Each resolves its client from a `ContextVar` in `_context.py`
rather than holding one:

- `OpenDotaAsyncClient.__aenter__` calls `bind_client(self)`; `__aexit__` calls `unbind_client()`.
  `activate()`/`deactivate()` expose the same thing outside `async with`.
- `active_client()` raises `OpenDotaError` with actionable text when nothing is bound, so calling
  `hero.get_stats()` outside a client scope fails loudly instead of silently.
- the method body is a one-line delegation to `client.get_hero_stat(hero_id=self.id)`. The client
  stays the only owner of fetching, caching, and normalization — relationship methods add no logic.

Why this shape, so it is not re-litigated:

- **models hold no client reference.** An earlier design stamped `_client` onto each `Hero` via
  `dataclasses.replace`. It was rejected because it produced two behavioural modes of the same type:
  structurally identical heroes where `get_stats()` worked on one and raised on the other, depending
  on invisible provenance. With the ambient binding every `Hero` behaves identically and success
  depends on *where* you call, not *which object* you hold.
- **the token stack is itself context-local.** `_token_stack` is a `ContextVar`, not an instance
  attribute, because two tasks sharing one client would otherwise pop each other's tokens and raise
  `Token was created in a different Context`. Nesting restores the outer client correctly.
- **`Hero` stays frozen with no new fields** — only methods were added, so equality, the assembler,
  and the `_make_heroes` pipeline are untouched. `Assembler` remains completely client-unaware, and
  `test_heroes_fixture.py` still drives `_make_heroes()` directly with no client in sight.
- no scope/handle object (`client.hero(id).get_stats()`) and no query/source/descriptor layer exists.
  Both were considered and rejected as more machinery than one relationship justifies; see §11.

### 6.3 Hero Item Popularity And Per-Key Caching

`/heroes/{hero_id}/itemPopularity` returns four objects — `start_game_items`, `early_game_items`,
`mid_game_items`, `late_game_items` — each `{item_id: count}`. Verified live and in OpenDota's
source (`getHeroItemPopularity` in `svc/util/queries.ts`), not assumed:

- the counts are **purchases** across the hero's **100 most recently parsed matches**, so one item
  can exceed 100. Phases are game-clock windows with cost floors: start ≤ 0:00 and ≤ 600 gold;
  early 0–10 min and ≥ 500; mid 10–25 min and ≥ 1,000; late ≥ 25 min and ≥ 2,000. OpenDota's API
  docs call this "professional games", but the query samples **any parsed match** — the docstrings
  say so, and should not repeat the docs' claim.
- an **unknown hero id is HTTP 200 with four empty phases**, indistinguishable from a hero with no
  parsed matches, so it is not an error; `HeroItemPopularity.is_empty` is how callers tell.

Shape and decisions:

- `HeroItemPopularity` has one list per phase (`start_game` … `late_game`) of `PopularItem(item,
  purchases)`, sorted most-purchased first, ties by item name. Four fields rather than a
  phase enum: nothing iterates phases generically yet (§3.4). `raw` is kept, because ids that fail to
  resolve are dropped from the lists and `raw` is the only place they survive.
- **the cross-domain join stays client-unaware:** the client fetches the payload and
  `get_items()` concurrently, then passes `items_by_id` into
  `Assembler.normalize_hero_item_popularity()` — the same pattern as `_make_heroes()` receiving its
  payloads. The assembler never fetches. Ids missing from the item constants (possible mid-patch)
  are dropped with **one WARNING per payload**, per §10.6; all ids resolved against live data and
  the vendored fixture when this was built.
- **id only, no `hero_name`.** `get_hero()`/`get_hero_stat()` resolve names for free from bulk
  payloads they hold; this endpoint has none, so a name parameter would hide a five-payload hero
  fetch behind a lookup. Name holders go `get_hero(hero_name=...)` → `Hero.get_item_popularity()`.
- **per-key caching, the first instance.** `_hero_item_popularity_cache` and
  `_hero_item_popularity_locks` are dicts keyed by hero id. Concurrent calls for one hero collapse to
  one request; different heroes fetch in parallel. A single shared lock would still pass a
  "fetches once" test while serializing every hero — `test_different_heroes_fetch_in_parallel_not_in_series`
  pins this by asserting peak concurrency, not elapsed time. The per-key lock is created with a
  get-then-insert that has no `await` in between, so racing tasks cannot end up with two locks for
  one hero.
- regression coverage mirrors items and heroes: recorded payloads for two heroes in
  `tests/fixtures/opendota_api/` are resolved against `tests/fixtures/items.json` in
  `test_item_popularity_fixture.py`.

### 6.4 Hero Matchups

`/heroes/{hero_id}/matchups` returns a JSON **list**, one `{hero_id, games_played, wins}` entry per
opposing hero (126 today). Verified live and in OpenDota's source (the route in `svc/api/spec.ts`,
not assumed):

- the query counts **premium/professional-league matches that started in the last year**, pairing
  the hero with each of the five heroes on the other team, so one match adds one game to each of
  five matchups. `wins` is matches the *queried* hero's team won. The `WHERE` clause in `spec.ts`
  only gives the window; the population comes from the writer: `upsertMatchPostgres` in
  `svc/util/insert.ts` stores a match in `matches` only when its `leagueid` is a `premium` or
  `professional` league (and, for api-type inserts, `isProMatch`). Public matches are not in the
  table, consistent with the fixture's small counts (Anti-Mage's top opponent has 92 games over a
  year). The docs do not say this; the docstrings do.
- an **unknown hero id is HTTP 200 with `[]`**, so it is not an error; `HeroMatchups.is_empty` is
  how callers tell.

Shape and decisions, copied by hand from §6.3 (§7):

- `HeroMatchup(hero, games_played, wins)` with `win_rate` (`None` when no games) and
  `HeroMatchups(hero_id, matchups, raw)` with `is_empty`; sorted most games first, ties by the
  opposing hero's localized name. Both frozen; `HeroMatchup.hero` is annotated `"Hero"` because
  `Hero` is defined after it and itself returns `HeroMatchups`.
- **client-unaware join:** the client fetches the payload and `get_heroes()` concurrently, then
  passes `heroes_by_id` into `Assembler.normalize_hero_matchups()`. Opposing ids missing from the hero
  constants are dropped with **one WARNING per payload** and survive only in `raw`. A missing or
  non-integer `hero_id`/`games_played`/`wins` raises `OpenDotaError` rather than becoming `0`.
- **id only, no `hero_name`**, and **per-key cache and lock** (`_hero_matchups_cache`/
  `_hero_matchups_locks`), exactly as §6.3 — pinned by the same peak-concurrency test shape.
- `Hero.get_matchups()` is a one-line delegation through the ambient client (§6.2).
- tests: `test_matchups.py` (assembler, client, relationship method, cache-fill log) and
  `test_matchups_fixture.py`, which resolves the recorded payloads in `tests/fixtures/opendota_api/`
  against the vendored hero constants.

Two per-key endpoints now exist (§6.3, §6.4) and their keying and lock lifecycle are identical, but
they are still two hand-written copies; see §7 for whether to extract.

---

## 7. Future Architecture Direction

The long-term direction may still include a session container and resource services, but those are **future moves**, not assumptions contributors should code against today.

If future work introduces:

- `Session`
- `PlayerService`
- `MatchService`
- `HeroService`
- further domain objects that own async relationship methods, beyond the three on `Hero` (§6.2–§6.4)

then that work should be introduced deliberately, with tests and updated docs, rather than implied by the instructions file alone.

`Hero.get_stats()` was introduced exactly that way and is the template to copy: declare the client
method that owns the fetch, then add a one-line delegating async method on the model. For new
entity-scoped endpoints that client method is private and the model method is the only public
entry point (§3.6).
`Hero.get_item_popularity()` and `Hero.get_matchups()` followed, written the same hand-rolled way; a
fourth should be too.

The per-key trigger has now fired **twice**: item popularity (§6.3) and matchups (§6.4) each needed
per-key single-flight, with identical keying (hero id) and lock lifecycle (never evicted, no
invalidation). Both endpoints joined a second domain, so the shared part is only the
get-or-create-lock-then-fill skeleton. That decision is the owner's, not something to fold into an
endpoint PR: do not extract it as part of adding `/durations` or `/benchmarks`. If one
of those needs different keying (e.g. `/benchmarks` with bracket/role) or invalidation, that is
evidence against a helper; if it matches again, propose the extraction as its own issue.

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
- `InvalidAPIKeyError` — subclass of `HTTPStatusError`. OpenDota rejects a bad key only as a
  400 whose JSON `error` names the API key, so `_rejected_key_reason()` matches on that body,
  and only when the request carried a key; any other 400 stays a plain `HTTPStatusError`
- `RateLimitError`
- `ResponseDecodeError`

Guidelines:

- fail with context
- preserve original exceptions with `from exc` when wrapping
- prefer typed SDK exceptions over generic `Exception`
- do not silently swallow malformed data or HTTP failures

### 8.1 Retry Behavior

Retries live in `http/_retry.py` and are driven by `AsyncHTTPTransport.request()`. The
contract, and why it is shaped this way:

- `build_retry_decorator()` returns a tenacity **`AsyncRetrying`**. This is load-bearing,
  not incidental: a synchronous `Retrying` handed an async callable returns the
  un-awaited coroutine, so the retry predicate inspects a coroutine object, never
  matches, and the real exception surfaces outside the retry loop. That bug shipped
  once and made `max_retries`/`backoff_factor`/`retry_on_status` silently inert while
  the errors guide (since removed, §13) promised users automatic retries. Do not swap it back.
- retries are decided **from the raised exception**, not from a returned response.
  `handle_response()` raises on any non-2xx status *inside* the retried callable, so a
  retryable status never comes back as a result — a `retry_if_result` predicate is
  unreachable by construction here.
- `TransportError` carries `is_timeout`, set by the transport, which catches
  `niquests.Timeout` ahead of `niquests.RequestException` (`Timeout` subclasses it, so
  the order matters). Without that flag `RetryPolicy.retry_on_timeout` cannot be honored,
  because every niquests failure is flattened into one SDK error type.
- `wait_exponential` uses `min=0` so `backoff_factor=0` genuinely means no wait. This *did*
  change the default: the first retry at `backoff_factor=0.5` now waits 0.5s instead of the
  1.0s the old `min=1` floor forced; later waits (1s, 2s, …) are unchanged. An earlier
  version of this file said the default was unaffected — it was wrong, and the test that
  should have caught it computed its expected values by hand. `test_backoff_factor_scales_the_wait`
  now asks tenacity for the real waits.
- each request drives a fresh `AsyncRetrying.copy()`. Attempt bookkeeping is per-call
  even on a shared object, so this is defensive rather than a fix for a live bug — but
  `statistics` *is* shared and clobbered across concurrent runs, and `get_heroes()` fans
  five requests through one transport.
- `tests/test_retry.py` counts calls against the underlying session. Attempt counts are
  the assertion that catches this class of bug; asserting only on the raised type does
  not.

### 8.2 Concurrency Cap And Rate Limits

**OpenDota never sends `Retry-After`.** Verified in its server source (`svc/web.ts`): a 429
carries only a JSON error body and the `X-Rate-Limit-Remaining-Minute` / `-Day` headers. The
minute counter is a fixed window that resets at every wall-clock minute boundary; limits are
60/min keyless, 300/min with a key, and 3,000/day keyless (keyed requests are billed rather
than refused). So "honor `Retry-After`" alone would be a no-op against the real API.
`_rate_limit_details()` in `_transport.py` therefore resolves a 429 in this order:

1. `X-Rate-Limit-Remaining-Day < 0` → daily quota; `is_daily_limit=True`, never retried, since
   no wait inside a request's lifetime helps.
2. `Retry-After` (delta-seconds or HTTP-date, the latter measured against the server's `Date`)
   → honored as-is. OpenDota does not send it, but a proxy in front of it may.
3. `X-Rate-Limit-Remaining-Minute < 0` → wait until the next minute on the **server's** clock
   (from `Date`), plus a 1s margin for the counter expiring on a different machine.
4. anything else → `retry_after=None`, ordinary exponential backoff.

How the waiting works, and why:

- the wait is a **cooldown deadline shared by every request on the client**
  (`AsyncHTTPTransport._resume_at`). OpenDota counts per key or IP, so a request sent during
  the cooldown would only be rejected too and burn one of its own attempts.
- each attempt takes a concurrency slot, then sits out any cooldown, then sends. The slot is
  held during the cooldown (nobody may send then anyway) but **released during exponential
  backoff**, so a request merely backing off never starves others. The cap is an
  `asyncio.Semaphore(max_concurrency)`; the default 10 matches niquests' connection pool
  (`pool_maxsize=10`), beyond which connections are opened and discarded rather than reused.
- after a rate limit with a known wait, tenacity's own backoff is **zero**, so the server's
  timing governs. Because the cooldown is an absolute deadline, a backoff would overlap it
  rather than add to it — but a backoff longer than the remaining cooldown would hold the
  retry past the moment the limit cleared.
- `is_retryable_rate_limit()` in `_retry.py` is the single rule for both the retry predicate
  and whether a cooldown is started. A 429 that will not be retried — daily quota, wait over
  `max_retry_after` (default 120s), or 429 removed from `retry_on_status` — starts **no**
  cooldown, so it fails fast for everyone instead of stalling other requests.
- every wait the transport takes, cooldown and tenacity backoff alike, goes through one seam
  (`_clock`, `_sleep`; backoff via `AsyncRetrying.copy(sleep=self._sleep)`). That is what lets
  the tests assert exact timings with a fake clock. An earlier draft left tenacity on real
  `asyncio.sleep`, and a test that claimed to check backoff timing silently checked nothing.

Known limit: a rate-limited retry still spends one of `max_retries`, and a request that 429s
re-queues behind others for a slot. A very large fan-out can therefore exhaust a request's
attempts across several windows. Proactive throttling from `X-Rate-Limit-Remaining-Minute`
(pausing before the quota runs out, rather than after a 429) would close that gap; it has
not been built.

---

## 9. Testing Strategy

### 9.1 Current Test Reality

The repo currently uses a flat test layout under `tests/`.

Existing coverage includes:

- config behavior
- auth behavior
- retry behavior, the concurrency cap, and rate-limit handling (`test_retry.py`), plus 429
  header parsing (`test_transport.py`); both retry and logging tests drive the transport through
  the shared fake-clock harness in `tests/_transport_harness.py`
- logging (`test_logging.py`): message text and level per event, no handlers installed, nothing
  raised is also logged loudly, and the API key never reaching a log line
- transport behavior
- item assembly, plus a regression sweep over every real item (`test_items_fixture.py`)
- hero merge/assembly, plus a regression sweep over every real hero (`test_heroes_fixture.py`)
- hero stats assembly (bracket folding, win rates, required-field errors)
- hero item popularity: assembler resolution/sorting/unresolved-id handling (`test_assembler.py`),
  a regression sweep over recorded real payloads (`test_item_popularity_fixture.py`), and
  client-level per-hero caching and parallelism (`test_client.py`)
- hero matchups: assembler resolution/sorting/unresolved-id warning, client per-hero caching,
  single-flight and parallelism, `Hero.get_matchups()`, and the cache-fill log (`test_matchups.py`),
  plus a regression sweep over recorded real payloads (`test_matchups_fixture.py`)
- ambient client binding and `Hero.get_stats()` (`test_context.py`), including nesting, the
  unbound-client error, and the gather-collapses-to-one-request property
- async client behavior

Do not rewrite the test structure preemptively unless there is a clear payoff.

### 9.2 Testing Expectations For New Work

For changes in the item or hero flow, prefer focused tests near the current pattern:

- raw record parsing tests
- assembler normalization tests
- client-level async behavior tests, including the cache/single-flight behavior under `asyncio.gather`
- for any new relationship method: that it raises without an active client, and that it delegates to
  the owning client method rather than reimplementing a fetch
- the feature's log events, per §10.6: asserted with `caplog` by exact message and level

If future player or match domains are added, test the vertical slice that actually exists rather than only internal helpers.

### 9.3 Validation Commands

Use the existing toolchain:

```bash
uv run pytest
uv run ruff check
uv run ty check
uv run zizmor .github/workflows   # only when touching workflows (§14)
```

For narrower work, run the smallest relevant subset first.

Always run `ruff check` and `ty check` on any file you touch and resolve issues before considering the work done, not just `pytest`. Pre-existing issues in files you did not touch may be left alone but should be called out rather than silently ignored.

`ruff check` includes the pydocstyle (`D`) rules in Google convention, so a new public
member without a docstring, or an `Args:` section that omits a parameter, fails lint (§10.4).
It also includes `G` and `LOG`, so an f-string or `.format()` log message, or a call through
the root logger, fails lint (§10.6).

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
- `Item`, `Hero`, `ItemAbility`, `HeroAbility`, `HeroTalent`, `HeroStats`, `HeroBracketStats`,
  `HeroItemPopularity`, `PopularItem`, `HeroMatchups`, `HeroMatchup`, and `Attribute` are all `frozen=True` — a
  deliberate decision (nothing in the codebase mutated a constructed instance, verified before freezing).
  Note this only blocks reassigning a field; it does not make nested `list`/`dict` fields (e.g. `raw`,
  `abilities`) immutable, and `hash()` on these models will raise since they hold unhashable list fields.
- models may own async relationship methods (§6.2) but must **not** own a client field. Keeping
  provenance out of the data is what makes two identically-built models interchangeable.
- derived values that callers would otherwise compute by hand belong on the model as properties
  (`Hero.innate_abilities`, `HeroStats.pub_win_rate`, `HeroBracketStats.win_rate`), returning `None`
  rather than raising or guessing when the inputs don't support an answer.

### 10.4 Docstring Conventions

All docstrings use **Google style**. This is enforced by ruff (`D` rules with
`convention = "google"` in `pyproject.toml`; `tests/` is exempt) and is the format the
planned MkDocs + mkdocstrings site will render, so it is not a stylistic preference.

- every public module, class, method, property, and function in `src/` has a docstring —
  ruff rejects missing ones, so a bare `ruff check` pass is the floor, not the goal
- dataclass models document their fields in an `Attributes:` section on the class docstring,
  not as `#` comments next to the fields; keep the entries in field order
- methods with parameters have an `Args:` section; anything returning a value has a
  `Returns:`; anything that deliberately raises has a `Raises:` listing the SDK error type
  (`OpenDotaError`, `ValueError`, ...) — the `get_*` methods on `OpenDotaAsyncClient` and
  the properties on `HeroStats` are the reference examples
- inline code uses single Markdown backticks (`` `Hero.get_stats()` ``), not reST double
  backticks, because the docs toolchain is Markdown-based
- prefer stating the contract callers depend on (`None` when the bracket has no picks;
  `False` means the item has no cooldown) over restating the type annotation
- internal (`_`-prefixed) modules follow the same format; they just are not rendered

### 10.5 Documentation Discipline

When the architecture changes, update:

- `AGENTS.md`
- public examples in `README.md` if affected
- tests that encode the intended usage

The instructions file must describe the current repo shape first and the future direction second.

### 10.6 Logging

**Every new feature ships with logging.** From `DEBUG`/`INFO` output alone, someone should be
able to reconstruct what the SDK did: what it fetched, what it retried, and why it paused. A
feature that adds network calls, caching, waiting, or a fallback path without log lines is
not done. `ruff` (`G`, `LOG`) enforces the call style; `tests/test_logging.py` and review
enforce the rest.

- **One logger per module:** `logger = logging.getLogger(__name__)`. They all sit under
  `opendota_sdk`, the one name users enable. Never log through the root logger.
- **Lazy `%`-style arguments**, never f-strings or `.format()` in the message:
  `logger.debug("Loaded %d items", len(items))`. Nothing is formatted when the level is off,
  and the constant message text groups cleanly in log aggregators.
- **Levels:**
  - `DEBUG` — per-request and per-attempt detail, and cache *fills*
    (`GET /heroStats -> 200 in 0.51s (attempt 1)`, `Loaded 127 heroes …`). Cache *hits* stay
    silent: a `gather` over every hero would otherwise drown the signal.
  - `INFO` — events that change timing the caller will notice: retries and rate-limit pauses.
  - `WARNING` — data problems the caller has no other way to learn about (a hero missing from
    the constants). Not for expected, handled conditions.
  - `ERROR`/`CRITICAL` — unused; anything that bad is raised.
- **Don't log what you raise.** An exception handed to the caller is theirs to report;
  logging it at `WARNING`+ as well reports it twice. A `DEBUG` line for the failed attempt is fine.
- **Log an event once, not once per waiter.** A burst of concurrent 429s logs one pause,
  emitted only when the cooldown deadline actually moves.
- **Never log secrets, headers, or bodies.** The API key travels in a request header, and
  OpenDota also accepts it as `?api_key=`. Transport lines therefore show the API-relative path
  via `_log_target()`, which redacts `api_key`, never `build_url()` output or headers. Failures
  are summarized with `_describe_failure()`, never `str(exc)`, because exception text can embed
  full URLs and response bodies. Objects that hold the key must not print it either:
  `OpenDotaClientConfig.api_key` is `field(repr=False)`, so a config that ends up in a log
  line, an f-string, or a traceback stays safe. Any new field holding a secret gets the same.
- **The library configures nothing:** no handlers, no `basicConfig`, no level changes. That
  includes `NullHandler`: with no handler, Python's last-resort handler still surfaces
  `WARNING` data problems for apps that configure no logging, and a `NullHandler` would
  silence them.
- **Test it.** Assert the feature's key events with `caplog`, by exact message and level.
  Anything that touches requests must keep `test_api_key_never_reaches_a_log_line` covering
  it. `tests/_transport_harness.py` drives the transport with a fake clock, so timings in
  messages are deterministic.

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
- do not re-add `Assembler.list_heroes()` for symmetry with `list_items()`/`list_hero_stats()`. It was
  removed because it could not do its job: it dropped `abilities_by_name`, so every hero it built got
  ability *stubs* (`"antimage_blink"` → `"Antimage Blink"`, no description, behaviors, mana cost, or
  cooldown). Heroes need the five-payload merge in `_make_heroes()` before normalization, so a
  raw-payload list method is the wrong shape for that flow — items and hero stats each arrive as one
  already-complete payload, heroes do not
- do not give models a `_client` field, or stamp one on with `dataclasses.replace`, to make
  relationship methods work — that design was evaluated and rejected (§6.2); the ambient `ContextVar`
  in `_context.py` is the mechanism
- do not document or scaffold a scope/handle layer (`client.hero(id).get_stats()`) or a
  query/source/executor layer as existing — both were designed out in favor of plain client methods
  plus one-line delegating model methods
- do not remove the `get_hero_stats()` cache in the name of freshness without replacing the
  single-flight it provides (§2.3)
- do not replace `AsyncRetrying` with a synchronous `tenacity.Retrying`, and do not move the
  retry predicate back to `retry_if_result` — both silently disable retries entirely while
  leaving the config knobs and the docs looking correct (§8.1)
- do not send the API key as `X-API-Key` (or any header other than `Authorization: Bearer`),
  and do not make the header name configurable. OpenDota ignores other headers *without error*,
  which is how every keyed request was silently served as anonymous for every release up to
  0.1.0a8 — verified in `svc/web.ts` and live. Do not move it to `?api_key=` either: the key
  would then sit in every request URL and in `HTTPStatusError.url`/its message. Tests pin the
  exact header on the wire (`test_auth.py`)
- do not add `hero_name` to per-hero endpoints like `get_hero_item_popularity()` "for symmetry",
  and do not collapse their per-hero locks into one shared lock. The first would hide a full hero
  fetch behind a lookup; the second would serialize every hero while still passing a naive
  "fetches once" test (§6.3)
- do not describe item popularity as professional-match data. OpenDota's docs say so, but its
  query samples the hero's last 100 parsed matches of any kind (§6.3)
- do not describe hero matchups as all-match or public-match data. The query reads the `matches`
  table, which only holds premium/professional-league matches (§6.4)
- do not reduce rate-limit handling to "honor `Retry-After`". OpenDota never sends that
  header; the minute-window wait in `_rate_limit_details()` is what actually fires (§8.2)
- do not make the rate-limit cooldown per-request, or hold the concurrency slot across
  exponential backoff. Both pass a naive "it retries" test while, respectively, burning
  attempts on doomed sends and starving other requests; each is pinned by a test (§8.2)
- do not describe `_transport.py` as having a sync implementation. `HTTPTransportBase` exists
  to share URL/header/response handling, not to leave room for a sync sibling (§2.1, §3.2)
- do not add handlers (including `NullHandler`), `logging.basicConfig()`, or level changes to
  library code, and do not log through the root logger. Output configuration belongs to the
  application (§10.6)
- do not log request headers, full URLs, response bodies, or `str(exc)` from the transport; any
  of them can carry the API key or a payload. Use `_log_target()` and `_describe_failure()` (§10.6)
- do not ship a feature that fetches, caches, waits, or falls back without log lines for those
  events, and do not log at `WARNING`+ an error that is also raised to the caller (§10.6)
- do not move examples ahead of implementation reality
- do not add a public client method for an endpoint about one modeled entity when a method on
  that model is its natural entry point; the client method that owns the fetch is private
  (§3.6)
- do not propose an endpoint whose result is an entity the SDK does not model yet, such as
  `Hero.get_players()` returning bare account ids before a players domain exists (§12.1)
- do not propose or build pro-scene endpoints (`/proMatches`, `/proPlayers`, `/teams/*`,
  `/leagues/*`) or endpoints that expose OpenDota's machinery rather than Dota data
  (`/explorer`, `/schema`, `/health`, `/metadata`, `/request/*`,
  `POST /players/{account_id}/refresh`), or `/live`. The owner put all three out of scope (§12.1)
- do not add hand-written guides back under `docs/` (§13). The owner removed them as useless
  and confusing; put usage detail in the docstrings, which the API reference renders
- do not add `mkdocs`, `mkdocs-material`, `mkdocs-gen-files`, or `mkdocs-literate-nav`
  back to the `docs` dependency group without a concrete need — the docs site runs on
  Zensical deliberately (§13); the latest releases of the last two pull in a package
  ("properdocs") this repo does not want as a dependency
- do not bump `version` in `pyproject.toml` by hand or replace the `0.0.0` placeholder —
  the release tag is the version and CI stamps it (§14). Hand bumps are how tags and
  versions drifted apart before, leaving four of seven alpha tags unpublished
- do not publish to TestPyPI from pull requests, and do not go back to run-id versions
  like `0.1.0-alpha.{run_id}` — the former breaks fork PRs and floods TestPyPI, the latter
  produced versions that outrank every real release (§14)
- do not re-enable the `setup-uv` cache in the workflows; zizmor's cache-poisoning audit
  rejects it because these workflows publish what they build
- do not loosen the gates in `agents.yml` (§15): no `allowed_non_write_users`, no
  `allowed_bots: '*'`, no `pull_request_target`, and no `if:` that drops the owner
  `sender.login` check. Each one lets someone other than the owner spend the API budget or
  start an implementation. Do not re-add an `environment:` with required reviewers to
  `implement` either: the owner chose the `approved` label as the single start approval,
  and a second click was tried and rejected as friction (§15)
- do not remove `revise`'s guard step or widen its `if:` beyond the owner's `@claude`
  comment. The action checks out the PR head itself, forks included, so without the guard
  an owner comment on a fork PR would run that fork's code with the job's secrets (§15)
- do not put the Claude app on the `protect-main` ruleset's bypass list, and do not add
  `.claude/agents/` roles that hold their own copy of the rules — the role files point at
  this file so there is exactly one rubric to drift from

If the implementation changes materially, update this file in the same work.

---

## 12. Near-Term Priorities

1. Keep the async client stable as the public entry point.
2. Continue polishing the item domain slice as the reference architecture.
3. Improve the hero flow without prematurely forcing a generalized service layer.
4. Introduce new domain entities only when their owning fetch, enrichment, and model path is clear.
5. `/itemPopularity` (§6.3) and `/matchups` (§6.4) are done. Add the remaining hero-scoped endpoints
   (`/durations` and `/benchmarks`) one at a time, hand-rolled per §7; `/players` waits for the
   players domain (§12.1); whether to
   extract the per-key caching is a separate decision (§7).
6. `README.md` has badges, a one-line description, the install line, and a link out to
   the docs site. It is also the PyPI landing page (`readme = "README.md"`), so the
   `async with` quickstart is the next thing worth adding.
7. Docs site: scaffolded, see §13. Keep the Google-style docstrings on the public API
   (§10.4) accurate — they're the site's actual content, not just source-level docs.
8. Agent workflow (§15): `implement`, `revise`, `review`, and `groom` exist. Keep folding
   what each run gets wrong back into §11 and the role files. The on-demand architect waits
   for the first proposal that needs design.

### 12.1 What New Work May Target

This is the scope the `product` role (§15) proposes from. It is the owner's to change, and
nothing outside it is proposed until the owner moves it here. Who the SDK is for: Python
developers building Dota 2 tools (README). It earns its place by returning typed, joined
objects instead of raw JSON (§1, §3.3), so new work is worth proposing when it gives a caller
data they would otherwise fetch and join by hand.

The universe of endpoints is OpenDota's OpenAPI spec at `https://api.opendota.com/api`: 55
paths in October 2026. The SDK covers `/heroes`, `/heroStats`, `/heroes/{id}/itemPopularity`,
`/heroes/{id}/matchups`, and the five `/constants/*` files the hero and item flows join.

**Only build on what exists.** A proposal may use only entities the SDK already models. An
endpoint whose natural result is an entity the SDK does not model yet waits for that domain,
however easy it looks: `/heroes/{id}/players` returns player account ids, so it waits for the
players domain rather than shipping bare ids as `Hero.get_players()`. Prefer work that
completes or hardens what exists over work that starts something new.

**Decided**, proposed in this order, one issue each:

1. the remaining hero-scoped endpoints whose results need only existing entities:
   `/heroes/{id}/durations` and `/benchmarks`
2. the README `async with` quickstart (§12.6)
3. the known limits this file already records: proactive throttling from
   `X-Rate-Limit-Remaining-Minute` (§8.2), and an explicit refresh or TTL for cached
   results (§2.3)

**Technical and maintenance work** may be proposed alongside the list above, at most one issue
per run so domain work is not crowded out. Each needs evidence in the repository, not taste:

- this file disagreeing with the code, such as a stale count, a renamed function, or a rule
  the code breaks
- a §9.2 test category missing for an existing feature, or a test that asserts timing or
  types where it should assert behavior (§8.1 and §6.3 have the history)
- a suppressed lint or type rule (`# noqa`, `# type: ignore`), or a docstring that misstates
  what the code does
- a public method that §3.6 says should be private, when no released caller depends on it

Not technical work for the groomer: dependency bumps (Renovate owns them), changes to
`.github/workflows/` or `.claude/` (the developer may not touch them, §15), refactors that
§3.4 calls speculative, or extracting a helper outside §7's condition.

**Out of scope.** The owner ruled these out in October 2026. Never propose them:

- the pro scene: `/proMatches`, `/proPlayers`, `/teams/*`, and `/leagues/*`. Matchups being
  pro-league data (§6.4) is a property of a hero endpoint, not a step into this area
- anything that is not domain-oriented, meaning it exposes OpenDota's own machinery rather
  than Dota data: `/explorer` (raw SQL), `/schema`, `/health`, `/metadata`, the parse-request
  queue (`GET /request/{jobId}`, `POST /request/{match_id}`), and
  `POST /players/{account_id}/refresh`. The SDK hands callers typed Dota objects (§3.1), never
  a query language or a job queue
- live games: `/live`

**Not decided.** Do not propose these until the owner moves them into the decided list:

- the next domain after heroes: players (`/players/*`, 14 read endpoints, plus
  `/heroes/{id}/players`) or matches (`/matches/{id}`, `/publicMatches`, `/parsedMatches`,
  `/heroes/{id}/matches`). Each brings a new domain model, so the first issue in either is a
  design question (§10.1), not an endpoint
- the domain-oriented long tail: `/search`, `/findMatches`, `/scenarios/*`,
  `/distributions`, `/rankings`, `/records/{field}`, and `/topPlayers`
- constants beyond the five files the SDK joins today

When every decided item has an issue, open or closed, the groomer proposes nothing and says
so in its run log. That is the signal for the owner to decide the next domain.

---

## 13. Documentation Site

A generated docs site lives under `docs/` (`mkdocs.yml` at the repo root), built with
**Zensical**, not `mkdocs` + `mkdocs-material`. This was a deliberate choice, not the
default: MkDocs 1.x is effectively unmaintained (18+ months with no release) and its
original maintainer is building an incompatible, closed-contribution "2.0" under the
same package name; the real Material for MkDocs team has moved on to Zensical as its
own Material-compatible successor. See `docs/gen_ref_pages.py`'s module docstring for
the full account, including a real, hands-on-verified supply-chain caution: recent
releases of `mkdocs-gen-files` and `mkdocs-literate-nav` pull in a package called
`properdocs` that prints an urgent-sounding build-time warning. Do not add either
package back as a dependency without re-reading that docstring first.

Current shape:

- the site is three things: `index.md`, `quickstart.md`, and the generated API reference.
  There are **no hand-written guides**. A `docs/guides/` folder with one page per domain
  slice existed until October 2026; the owner removed it as useless and confusing, because
  each page restated docstrings and drifted from them. The docstrings (§10.4) are the
  documentation, so a feature documents itself there and in this file, not in a guide.
- `docs/gen_ref_pages.py` is a **plain pre-build script**, not a plugin — Zensical
  doesn't support the mkdocs-gen-files plugin API. It writes real files to `docs/api/`
  (gitignored, regenerated every build) from `opendota_sdk.__all__`, so the API
  reference always matches the actual public surface regardless of which internal
  module a symbol is defined in (`_config.py`, `_errors.py` included).
- `mkdocs.yml` is read directly by Zensical (`zensical build -f mkdocs.yml`) in its
  documented mkdocs-compatible mode — there is no separate `zensical.toml`. Don't add
  one speculatively; migrate only if a feature genuinely needs the native config format.
- The only docs dependencies are `zensical` and `mkdocstrings-python` — deliberately not
  `mkdocs`, `mkdocs-material`, `mkdocs-gen-files`, or `mkdocs-literate-nav`. Zensical
  reimplements literate-nav's `SUMMARY.md` convention natively and needs none of them.
- CI lives in its own `.github/workflows/docs.yml`, separate from `ci.yml`, triggered
  only by changes under `docs/`, `src/`, `mkdocs.yml`, or the dependency files. Its
  `docs` job runs `gen_ref_pages.py` then `zensical build -f mkdocs.yml --strict`,
  which fails the build on broken cross-refs or missing pages — same purpose as the
  item/hero regression fixtures serve for code. On a release tag push (`v*`), a separate
  `docs-deploy` job publishes to GitHub Pages via the native Actions flow
  (`actions/upload-pages-artifact` + `actions/deploy-pages`), so the site documents what
  is on PyPI, not unreleased `main`. That requires the repository's Pages source set to
  "GitHub Actions" and a `v*` tag rule on the `github-pages` environment — repo
  settings, not something CI or an agent can set on its own.

---

## 14. Release Process

Releasing is one step: push a `v` tag.

```bash
git tag v0.1.0-alpha.8 && git push origin v0.1.0-alpha.8
```

There is no version bump commit. `pyproject.toml` holds `version = "0.0.0"` as a
placeholder because `uv_build` requires a static version and cannot read one from git
(upstream: astral-sh/uv#14037). `ci.yml`'s build job stamps the real version with
`uv version --frozen` right before `uv build`, so the tag cannot disagree with the built
version. One consequence: `opendota_sdk.__version__` reports `0.0.0` in a dev checkout;
wheels report the real version.

What `ci.yml` does per trigger:

| Trigger | Version stamped | TestPyPI | PyPI | GitHub Release |
|---|---|---|---|---|
| pull request | none (`0.0.0`) | — | — | — |
| push to `main` | `<last v tag>.post0.dev<run number>` | yes | — | — |
| tag `v*` | the tag, normalised (`v0.1.0-alpha.8` → `0.1.0a8`) | yes | in parallel with TestPyPI | after PyPI |

- one build per run; the same files go to TestPyPI, PyPI, and the GitHub Release, after
  an import smoke test of the wheel in a clean environment
- TestPyPI on every push to `main` is a deliberate health check of the publishing path
  (OIDC trust, the publish action, metadata acceptance). Renovate automerges action
  updates, so a broken publish shows up the same day rather than on release day.
  `skip-existing` covers re-runs, which keep their run number. On tags it runs in
  parallel with PyPI rather than gating it, so a TestPyPI outage cannot block a release;
  a failure there still turns the run red
- the workflow triggers on **every** tag and fails tags without the `v` prefix, rather
  than ignoring them; `uv version` rejects tags that are not valid versions
- release notes come from git-cliff (`release` dependency group, configured under
  `[tool.git-cliff]` in `pyproject.toml`) over the Conventional Commits since the previous
  `v` tag: breaking changes, features, fixes, performance, and runtime (`deps(main)`)
  dependency bumps. Other commit types are omitted, so a commit that should appear in the
  notes needs a matching prefix. There is no `CHANGELOG.md`; the Releases page is the changelog
- PyPI and TestPyPI use Trusted Publishing, bound to `ci.yml` and the `pypi`/`testpypi`
  environments. Renaming the workflow or those environments breaks publishing until the
  trusted publisher on (Test)PyPI is updated to match
- workflows run with `contents: read` by default, write scopes only per job, no persisted
  checkout credentials, and no `setup-uv` cache; `zizmor` audits them in CI and in prek

---

## 15. Agent Workflow

Feature work can be delegated to Claude Code running in GitHub Actions
(`.github/workflows/agents.yml`, the Claude Code Action pinned by SHA). This file is the
constitution for every role; the role prompts under `.claude/agents/` are thin and point at
sections here rather than restating them. They also register as Claude Code subagents for
local use.

**Current:**

- `implement` — the `developer` role. Fires when the repository owner adds `approved` or
  `design-approved` to an issue. It posts a plan comment, implements on a `claude/` branch
  copying the nearest existing pattern, runs the §9.3 commands, updates this file per §10.5,
  and opens the PR itself with a Conventional Commits title. It never touches the version,
  the workflows, or `.claude/`.
- `revise` — the `developer` role again, sent back to its own PR. Fires when the owner
  comments `@claude` on a PR. A guard step runs before any PR code is fetched and fails the
  job unless the PR is open and its head is a `claude/` branch in this repository, because
  the action would otherwise check out a fork's head with the job's secrets. The owner's
  comment is the whole task; the developer commits to the same branch, and the push re-runs
  `review`. It shares `implement`'s concurrency queue. It may read the PR conversation
  (`gh pr view`, and `gh api` on any PR's review-comments endpoint) so it can see the
  reviewer's findings.
  The owner chose that knowing it exposes the model to comments from anyone on a public
  repo; the role file treats every comment except the owner's as information only.
- `review` — the `reviewer` role. Fires on every PR whose head is in this repository, except
  Renovate's. It reads every changed file, checks the diff against §11, §5/§6, §10.6, §9.2,
  §10.4, and §10.5 in that order, verifies data claims against fixtures and OpenDota's
  source with the same two `curl` forms the developer has, runs the validation commands,
  and reports inline findings tagged blocking/nit. It edits nothing and cannot approve.
  Its first real review (#87) passed in 9 turns after skipping the docs changes and every
  data claim, and missed docstrings calling pro-league matchups "every match". The role now
  treats anything unread or unverified as a blocking finding.

- `groom` — the `product` role. Runs every Monday at 07:00 UTC, and on demand from the
  Actions tab (`workflow_dispatch`, owner only). It proposes from §12.1 only: domain work that
  builds on entities the SDK already models, and at most one technical or maintenance issue
  per run backed by quoted evidence. It verifies each domain candidate's payload live and its
  population in OpenDota's source, and opens at most three issues labeled `proposal`, each
  with a usage example of the proposed surface and a design-level plan. It creates nothing
  while three proposals are waiting for the owner. A `proposal` label starts nothing; the
  owner reads the issue and adds `approved`. The owner chose to build it after one
  end-to-end endpoint run (#80/#87), rather than after all the §12.5 endpoints as an
  earlier version of this section planned.

**Planned, not built:** an on-demand `design` job (the `architect` role, on `needs-design`,
posting options and a recommendation; the owner then labels `design-approved`). It waits for
the first proposal that needs design, most likely the first issue in a new domain (§12.1).

**Gates, and why each exists.** Only the owner can start or ship an implementation:

1. The action refuses to run for actors without write access, so issues, comments, and
   labels from anyone else never start a run. Fork PRs receive no secrets. The `review`
   job allows exactly two bot logins, the Claude app's, because PRs the developer opens
   arrive with that actor.
2. `implement` checks `sender.login` is the owner and the label is one of the two. The
   label is the whole start approval: adding it starts the build immediately. An earlier
   version also parked the job on an `agent-build` environment with the owner as required
   reviewer, so every run needed a second Approve click in the Actions UI; the owner
   dropped that as friction with no security gain, since only the owner can add the label
   in the first place. The environment still exists in the repo settings but nothing
   references it.
3. The `protect-main` ruleset requires a PR, green CI, and an owner review. Its bypass
   list holds two entries, both in pull-request mode: Renovate, so dependency automerge
   works, and the Repository admin role, because GitHub never lets a PR's author approve
   it and the owner is the only code owner — without that entry the owner's own PRs could
   never merge. The Claude app is on neither list, so it can push `claude/*` branches but
   never merge. On agent PRs the owner still approves rather than bypassing, so the
   review is recorded.
4. Spend is bounded three ways: one `implement` at a time (`concurrency`), `--max-turns`
   and `timeout-minutes` per job, and the runs drawing on the owner's Claude subscription
   through a `claude setup-token` OAuth token (`CLAUDE_CODE_OAUTH_TOKEN`), whose plan limits
   are the ceiling. An API key was tried first and every run was rejected with "Credit
   balance is too low", although the Console organization held the monthly API credit
   that comes with the Max plan: that credit explicitly excludes Claude Code, and the
   action is Claude Code. Do not switch back to `anthropic_api_key` without buying
   Console credit. Only the owner's comments reach the model (`include_comments_by_actor`).
5. Network access for `implement` is two literal `curl -sS` prefixes, one for
   `api.opendota.com/api/` and one for `raw.githubusercontent.com/odota/`, so the developer
   can record real fixtures and read OpenDota's source (§6.3). The first real run stopped
   without them rather than invent data, which is the behavior to keep. The rules end in a
   bare `*` (`Bash(curl -sS https://api.opendota.com/api/*)`), never `:*`: Claude Code reads
   `:*` as a space followed by `*`, so `.../api/:*` only matches when a space follows `api/`,
   which no real URL has. That spelling shipped once and denied every fetch. `WebFetch` stays
   off: the action bans it by default, and it summarizes pages through a small model, so it
   cannot record raw JSON. The tool allowlist is not the real boundary, though:
   `Bash(uv run:*)` already lets the agent run code with network access. What protects the
   subscription token is `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` on both jobs, which strips
   credentials from every subprocess while leaving GitHub tokens for `gh`. Do not remove it.
   The scrub needs `bubblewrap`, and Claude Code refuses to start without it. The action
   installs it only when `allowed_non_write_users` is set, which this workflow never sets,
   so each job has its own "Install subprocess isolation dependencies" step copied from the
   action. The first run with the scrub on failed at startup for exactly this reason.
6. `groom` cannot execute code: it has no `uv`, no `Bash(uv run:*)`, no git tools, and
   `contents: read`. It reads the repository, lists and creates issues, and uses the same
   read-only `curl` forms, plus the bare spec URL. It does read issue and PR titles written by
   anyone on a public repo, so a prompt injection could at worst produce a bad `proposal`
   issue, which starts nothing. Do not give it `uv run`, write access to code, or any label
   but `proposal`.

Labels: `proposal` (groomer output, nothing runs), `needs-design` (architect, planned),
`design-approved` and `approved` (implement). The action restores `.claude/` and `CLAUDE.md`
from the base branch when it runs on a PR, so a PR cannot rewrite a role file. `AGENTS.md`
is **not** on that restored list: a PR can edit the rubric the reviewer reads. That is
acceptable only because the reviewer's tools are read-only and the owner still reviews
the `AGENTS.md` diff itself before merging; do not give the `review` job write tools.

---

## 16. References

- [OpenDota API Docs](https://docs.opendota.com/)
- [dotaconstants Repository](https://github.com/odota/dotaconstants)
- [Python AsyncIO Best Practices](https://docs.python.org/3/library/asyncio.html)
- [Zensical Documentation](https://zensical.org/docs/)
