# OpenDota SDK — Agent Instructions

**Status**: Alpha, architecture still settling  
**Current focus**: Async client foundation, item domain vertical slice, hero model flow, hero stats slice  
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
- one relationship method, `Hero.get_stats()`, resolved through an ambient client (§6.2)
- typed `Item`, `Hero`, and `HeroStats` models
- internal transport, auth, retry, and error layers

Planned but not implemented yet:

- player domain objects
- match domain objects
- service-per-resource architecture
- session container abstraction
- relationship navigation beyond the single `Hero.get_stats()` case — no descriptor, query,
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

Domain objects that need network access expose it as an async method — `Hero.get_stats()` is the
first and currently only instance (§6.2).

### 3.3 Internal Enrichment

The SDK should absorb enrichment logic so callers do not manually join API payloads with dotaconstants.

Current examples:

- `OpenDotaAsyncClient.get_items()` returns typed `Item` objects assembled from constants payloads
- `OpenDotaAsyncClient.get_heroes()` merges `/heroes` with `/constants/heroes` and returns typed `Hero` models
- `OpenDotaAsyncClient.get_hero_stats()` folds `/heroStats`'s flat `{bracket}_pick`/`{bracket}_win` keys
  into typed `HeroBracketStats` entries and derives win rates, instead of exposing the raw numeric keys

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
- selected user-facing models like `Item`, `Hero`, and `HeroStats`, plus the enums they expose
  (`HeroSkillBracket` is exported because `HeroBracketStats.bracket` hands it to callers)

The ambient-client helpers in `_context.py` are **not** exported: `active_client()`, `bind_client()`,
and `unbind_client()` are internal. Users reach them through `async with client` or
`client.activate()`.

Avoid exporting internal helpers, registries, transport classes, or normalization machinery.

---

## 4. Current Module Map

```text
src/opendota_sdk/
├── __init__.py          # Public exports only
├── _config.py           # Client and transport configuration
├── _context.py          # Ambient active-client binding for model relationship methods
├── _errors.py           # SDK-specific exception types
├── _records.py          # Raw item record boundary before assembly
├── assembler.py         # Item, hero, and hero-stats normalization and assembly
├── client.py            # OpenDotaAsyncClient (owns all raw fetching and caching)
├── enums.py             # Hero-related enums and shared enum types
├── models.py            # Typed Item, Hero, and HeroStats models, plus item enums
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

`Hero.get_stats()` is the SDK's **only** relationship method today. It resolves its client from a
`ContextVar` in `_context.py` rather than holding one:

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

---

## 7. Future Architecture Direction

The long-term direction may still include a session container and resource services, but those are **future moves**, not assumptions contributors should code against today.

If future work introduces:

- `Session`
- `PlayerService`
- `MatchService`
- `HeroService`
- further domain objects that own async relationship methods, beyond `Hero.get_stats()` (§6.2)

then that work should be introduced deliberately, with tests and updated docs, rather than implied by the instructions file alone.

`Hero.get_stats()` was introduced exactly that way and is the template to copy: declare the client
method that owns the fetch, then add a one-line delegating async method on the model. A second and
third relationship should be written the same hand-rolled way. Only once that delegation has visibly
repeated — and once per-key endpoints like `/heroes/{id}/matchups` force per-key single-flight, which
the current bulk cache+lock does not cover — is a shared abstraction worth extracting.

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
- item assembly, plus a regression sweep over every real item (`test_items_fixture.py`)
- hero merge/assembly, plus a regression sweep over every real hero (`test_heroes_fixture.py`)
- hero stats assembly (bracket folding, win rates, required-field errors)
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

`ruff check` includes the pydocstyle (`D`) rules in Google convention, so a new public
member without a docstring, or an `Args:` section that omits a parameter, fails lint (§10.4).

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
- `Item`, `Hero`, `ItemAbility`, `HeroAbility`, `HeroTalent`, `HeroStats`, `HeroBracketStats`, and
  `Attribute` are all `frozen=True` — a
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
- do not move examples ahead of implementation reality
- do not add `mkdocs`, `mkdocs-material`, `mkdocs-gen-files`, or `mkdocs-literate-nav`
  back to the `docs` dependency group without a concrete need — the docs site runs on
  Zensical deliberately (§13); the latest releases of the last two pull in a package
  ("properdocs") this repo does not want as a dependency

If the implementation changes materially, update this file in the same work.

---

## 12. Near-Term Priorities

1. Keep the async client stable as the public entry point.
2. Continue polishing the item domain slice as the reference architecture.
3. Improve the hero flow without prematurely forcing a generalized service layer.
4. Introduce new domain entities only when their owning fetch, enrichment, and model path is clear.
5. Add the remaining hero-scoped endpoints (`/heroes/{id}/matchups`, `/durations`, `/players`,
   `/itemPopularity`) one at a time, hand-rolled per §7, and let the per-key caching need that emerges
   there decide whether a shared abstraction is warranted.
6. `README.md` still documents none of this — it is badges and a one-line description only.
7. Docs site: scaffolded, see §13. Keep the Google-style docstrings on the public API
   (§10.4) accurate — they're the site's actual content, not just source-level docs.

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
  item/hero regression fixtures serve for code. On push to `main`, a separate
  `docs-deploy` job publishes to GitHub Pages via the native Actions flow
  (`actions/upload-pages-artifact` + `actions/deploy-pages`), which requires the
  repository's Pages source to be set to "GitHub Actions" once in repo
  settings — not something CI or an agent can set on its own.

---

## 14. References

- [OpenDota API Docs](https://docs.opendota.com/)
- [dotaconstants Repository](https://github.com/odota/dotaconstants)
- [Python AsyncIO Best Practices](https://docs.python.org/3/library/asyncio.html)
- [Zensical Documentation](https://zensical.org/docs/)
