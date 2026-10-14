"""Regression sweep: real `/heroes/{id}/matchups` payloads against real heroes.

Mirrors `test_item_popularity_fixture.py`. The payloads are recorded API responses
(`tests/fixtures/opendota_api/`), resolved against the heroes built from the vendored
dotaconstants, so a change to either shape -- or an assembler change that drops or
misreads entries -- fails here rather than in a user's program.
"""

import json
import logging

import pytest

from opendota_sdk.assembler import Assembler

from .conftest import FIXTURES_DIR
from .test_heroes_fixture import HEROES

API_FIXTURES = FIXTURES_DIR / "opendota_api"
HEROES_BY_ID = {hero.id: hero for hero in HEROES}


@pytest.mark.parametrize("hero_id", [1, 74])
def test_every_real_entry_resolves_to_a_hero_with_its_counts(hero_id, caplog):
    raw = json.loads((API_FIXTURES / f"hero_{hero_id}_matchups.json").read_text())

    with caplog.at_level(logging.WARNING, logger="opendota_sdk"):
        result = Assembler().normalize_hero_matchups(
            raw, hero_id=hero_id, heroes_by_id=HEROES_BY_ID
        )

    assert caplog.records == [], "every opposing hero id resolves"
    assert result.hero_id == hero_id
    assert not result.is_empty
    assert {m.hero.id: (m.games_played, m.wins) for m in result.matchups} == {
        entry["hero_id"]: (entry["games_played"], entry["wins"]) for entry in raw
    }
    games = [m.games_played for m in result.matchups]
    assert games == sorted(games, reverse=True)
    assert all(m.win_rate is not None and 0 <= m.win_rate <= 1 for m in result.matchups)
