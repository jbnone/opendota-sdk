"""Regression sweep: real `/heroes/{id}/itemPopularity` payloads against real items.

Mirrors `test_items_fixture.py` and `test_heroes_fixture.py`. The payloads are recorded
API responses (`tests/fixtures/opendota_api/`), resolved against the vendored item
constants, so a change to either shape -- or an assembler change that drops or misreads
entries -- fails here rather than in a user's program.
"""

import json
from pathlib import Path

import pytest

from opendota_sdk.assembler import Assembler

API_FIXTURES = Path(__file__).parent / "fixtures" / "opendota_api"
PHASES = (
    ("start_game_items", "start_game"),
    ("early_game_items", "early_game"),
    ("mid_game_items", "mid_game"),
    ("late_game_items", "late_game"),
)


@pytest.fixture(scope="module")
def items_by_id(real_items_json):
    raw_items = [{**data, "name": name} for name, data in real_items_json.items()]
    return {item.id: item for item in Assembler().list_items(raw_items)}


@pytest.mark.parametrize("hero_id", [1, 74])
def test_every_real_entry_resolves_to_an_item_with_its_count(hero_id, items_by_id):
    raw = json.loads(
        (API_FIXTURES / f"hero_{hero_id}_item_popularity.json").read_text()
    )

    popularity = Assembler().normalize_hero_item_popularity(
        raw, hero_id=hero_id, items_by_id=items_by_id
    )

    assert popularity.hero_id == hero_id
    assert not popularity.is_empty
    for payload_key, field_name in PHASES:
        entries = getattr(popularity, field_name)
        expected = {int(item_id): count for item_id, count in raw[payload_key].items()}
        assert {entry.item.id: entry.purchases for entry in entries} == expected
        purchases = [entry.purchases for entry in entries]
        assert purchases == sorted(purchases, reverse=True)


def test_real_anti_mage_build_reads_as_expected(items_by_id):
    """A human-checkable anchor: Anti-Mage farms Battle Fury mid-game."""
    raw = json.loads((API_FIXTURES / "hero_1_item_popularity.json").read_text())

    popularity = Assembler().normalize_hero_item_popularity(
        raw, hero_id=1, items_by_id=items_by_id
    )

    mid_game = [entry.item.name for entry in popularity.mid_game]
    assert "bfury" in mid_game[:5]
    assert popularity.start_game[0].item.name == "branches"
