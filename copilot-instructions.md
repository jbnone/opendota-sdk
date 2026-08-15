# OpenDota SDK — Copilot Instructions

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

- `ConstantsRegistry` exists today in `src/opendota_sdk/constants.py`
- it is used internally by `OpenDotaAsyncClient`
- it should **not** be exported from `__init__.py`
- contributors should avoid designing user workflows around direct registry access

For items specifically, constants are fetched lazily from the OpenDota constants route and cached in memory per client instance.

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
├── client.py            # OpenDotaAsyncClient
├── constants.py         # Internal constants registry for items
├── enums.py             # Hero-related enums and shared enum types
├── models.py            # Typed Item and Hero models, plus item enums
├── http/
│   ├── _auth.py         # Header-based auth handling
│   ├── _retry.py        # Retry policy and decorator builder
│   └── _transport.py    # Sync/async transport implementations
└── resources/           # Reserved for future resource/service modules
```

Notes:

- `resources/` is not yet a real service layer. Do not assume `PlayerService`, `HeroService`, or `BaseService` exist.
- `models.py` currently contains public-facing dataclasses and item enums despite its generic name.
- `constants.py` currently holds an internal registry implementation, not public enum definitions.

---

## 5. Item Slice Is The Reference Pattern

The item flow is the current proof of concept for the broader SDK direction.

### 5.1 Current Item Pipeline

```text
OpenDota constants route
    -> ConstantsRegistry
    -> ItemRecord
    -> Assembler
    -> Item
    -> OpenDotaAsyncClient.get_items()
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

- start at `assembler.py`, `_records.py`, `constants.py`, `models.py`, or `client.py`
- preserve the raw-record -> assembler -> model flow
- add focused tests before widening scope

---

## 6. Hero Flow Guidance

Heroes currently follow a lighter path than items.

Current shape:

- `OpenDotaAsyncClient.get_heroes()` fetches `/heroes`
- it also fetches `/constants/heroes`
- `ClientLogicMixin.make_heroes()` merges the two payloads
- the client returns typed `Hero` dataclasses directly

Implications:

- hero enrichment logic currently lives closer to the client than the item flow does
- if hero functionality expands, it may eventually need a dedicated assembly path
- do not force heroes into the item architecture mechanically unless the duplication is real and justified

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
```

For narrower work, run the smallest relevant subset first.

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

### 10.4 Documentation Discipline

When the architecture changes, update:

- `copilot-instructions.md`
- public examples in `README.md` if affected
- tests that encode the intended usage

The instructions file must describe the current repo shape first and the future direction second.

---

## 11. Anti-Drift Rules

When editing this project, do not introduce instruction drift in these areas:

- do not document `Session` as current API unless it exists in code
- do not document sync clients as supported
- do not describe `resources/` as implemented when it is still mostly reserved
- do not describe `constants.py` as public API when the registry is internal
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
