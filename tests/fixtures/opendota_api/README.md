# Recorded OpenDota API responses

Verbatim responses from the live OpenDota API, used as real-shaped fixtures for
endpoints that are not part of dotaconstants (those live in `../dotaconstants/`).

| File | Endpoint | Recorded |
|---|---|---|
| `hero_1_item_popularity.json` | `GET /api/heroes/1/itemPopularity` (Anti-Mage) | 2026-10-07 |
| `hero_74_item_popularity.json` | `GET /api/heroes/74/itemPopularity` (Invoker) | 2026-10-07 |
| `hero_1_matchups.json` | `GET /api/heroes/1/matchups` (Anti-Mage) | 2026-10-14 |
| `hero_74_matchups.json` | `GET /api/heroes/74/matchups` (Invoker) | 2026-10-14 |
| `hero_1_benchmarks.json` | `GET /api/benchmarks?hero_id=1` (Anti-Mage) | 2026-10-17 |
| `hero_74_benchmarks.json` | `GET /api/benchmarks?hero_id=74` (Invoker) | 2026-10-17 |
| `hero_99999_benchmarks.json` | `GET /api/benchmarks?hero_id=99999` (unknown hero: every value `null`) | 2026-10-17 |

Every item id in these files resolves against `../items.json`, which the regression
test relies on. Point-in-time snapshots, not a live dependency: re-record them, and
check they still resolve, if the payload shape changes.
