# Recorded OpenDota API responses

Verbatim responses from the live OpenDota API, used as real-shaped fixtures for
endpoints that are not part of dotaconstants (those live in `../dotaconstants/`).

| File | Endpoint | Recorded |
|---|---|---|
| `hero_1_item_popularity.json` | `GET /api/heroes/1/itemPopularity` (Anti-Mage) | 2026-10-07 |
| `hero_74_item_popularity.json` | `GET /api/heroes/74/itemPopularity` (Invoker) | 2026-10-07 |

Every item id in these files resolves against `../items.json`, which the regression
test relies on. Point-in-time snapshots, not a live dependency: re-record them, and
check they still resolve, if the payload shape changes.
