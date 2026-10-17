"""Regression sweep keeping `HeroName` in step with the vendored dotaconstants heroes."""

import json
import re

import pytest

from opendota_sdk import HeroName

from .conftest import FIXTURES_DIR

REAL_HEROES: list[dict] = list(
    json.loads(
        (FIXTURES_DIR / "dotaconstants" / "heroes.json").read_text(encoding="utf-8")
    ).values()
)


def _member_name(localized_name: str) -> str:
    """The naming rule `HeroName` follows: drop apostrophes, join words with underscores."""
    return (
        re.sub(r"[^A-Za-z0-9]+", "_", localized_name.replace("'", ""))
        .strip("_")
        .upper()
    )


def test_every_fixture_hero_has_exactly_one_member():
    fixture_names = {hero["name"] for hero in REAL_HEROES}
    enum_values = {member.value for member in HeroName}

    missing = sorted(fixture_names - enum_values)
    stale = sorted(enum_values - fixture_names)

    assert not missing, (
        "heroes in the fixture with no HeroName member; add: "
        + ", ".join(
            f'{_member_name(h["localized_name"])} = "{h["name"]}"'
            for h in REAL_HEROES
            if h["name"] in missing
        )
    )
    assert not stale, f"HeroName members with no hero in the fixture: {stale}"
    assert len(HeroName) == len(REAL_HEROES)


@pytest.mark.parametrize("hero", REAL_HEROES, ids=lambda hero: hero["localized_name"])
def test_member_is_named_after_the_heros_in_game_name(hero):
    assert HeroName[_member_name(hero["localized_name"])] == hero["name"]


def test_tricky_names_follow_the_rule():
    assert HeroName.ANTI_MAGE == "npc_dota_hero_antimage"
    assert HeroName.NATURES_PROPHET == "npc_dota_hero_furion"
    assert HeroName.ZEUS == "npc_dota_hero_zuus"


def test_members_are_plain_strings_equal_to_the_internal_name():
    for member in HeroName:
        assert isinstance(member, str)
        assert member == member.value
        assert hash(member) == hash(member.value)
