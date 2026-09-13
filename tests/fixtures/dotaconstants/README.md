# Vendored dotaconstants data

Static snapshot of build outputs from [odota/dotaconstants](https://github.com/odota/dotaconstants), used as real-shaped test fixtures for the hero domain (mirrors the existing `tests/fixtures/items.json` pattern for items).

- Source: `https://github.com/odota/dotaconstants`
- Commit: `e7705ee975ebec2a88a59a7b455d4cae5dc69ca1` (2026-07-28)
- License: MIT (see `LICENSE` in this directory), Copyright (c) 2017 The OpenDota Project

Files:
- `heroes.json` — hero constants, source for `/constants/heroes`
- `hero_abilities.json` — per-hero ability/talent/facet name references
- `abilities.json` — per-ability data (title, description, behavior, attributes, ...), cross-referenced by name from `hero_abilities.json`
- `hero_lore.json` — per-hero lore text

These are point-in-time snapshots, not a live dependency — update by re-fetching from the source repo if newer data is needed.
