"""Regression sweep validating the hero merge + assembler pipeline against real dotaconstants data."""

import json

import pytest

from opendota_sdk.assembler import Assembler
from opendota_sdk.client import OpenDotaAsyncClient
from opendota_sdk.enums import HeroRole
from opendota_sdk.models import (
    AbilityBehavior,
    DamageType,
    HeroAbility,
    HeroAttackType,
    HeroPrimaryAttribute,
    HeroTalent,
)

from .conftest import FIXTURES_DIR

DOTACONSTANTS_FIXTURES_DIR = FIXTURES_DIR / "dotaconstants"


def _load(name: str) -> dict:
    return json.loads((DOTACONSTANTS_FIXTURES_DIR / name).read_text(encoding="utf-8"))


# Loaded at module scope (not fixtures) so hero names are available for parametrize ids,
# and so the merge pipeline runs once for the whole sweep rather than once per test.
REAL_HEROES_CONSTANTS: dict[str, dict] = _load("heroes.json")
REAL_HERO_ABILITIES: dict[str, dict] = _load("hero_abilities.json")
REAL_ABILITIES: dict[str, dict] = _load("abilities.json")
REAL_HERO_LORE: dict[str, str] = _load("hero_lore.json")

# There is no standalone /heroes fixture. In the real API, /heroes and /constants/heroes
# share the same per-hero stat fields (client._make_heroes merges them id-by-id, with the
# /heroes side taking precedence), so the constants payload is a realistic stand-in for the
# /heroes list here too.
HEROES = OpenDotaAsyncClient._make_heroes(
    heroes_api=list(REAL_HEROES_CONSTANTS.values()),
    heroes_constants=REAL_HEROES_CONSTANTS,
    hero_abilities=REAL_HERO_ABILITIES,
    abilities=REAL_ABILITIES,
    hero_lore=REAL_HERO_LORE,
    assembler=Assembler(),
)
HEROES_BY_NAME = {hero.name: hero for hero in HEROES}


@pytest.mark.parametrize("name", list(HEROES_BY_NAME.keys()))
def test_make_heroes_normalizes_every_real_hero_without_raising(name):
    hero = HEROES_BY_NAME[name]

    assert hero.id >= 0
    assert isinstance(hero.name, str) and hero.name != ""
    assert isinstance(hero.localized_name, str) and hero.localized_name != ""
    assert isinstance(hero.primary_attribute, HeroPrimaryAttribute)
    assert isinstance(hero.attack_type, HeroAttackType)
    assert all(isinstance(role, HeroRole) for role in hero.roles)
    assert isinstance(hero.lore, str) and hero.lore != ""

    assert all(isinstance(ability, HeroAbility) for ability in hero.abilities)
    assert all(
        isinstance(behavior, AbilityBehavior)
        for ability in hero.abilities
        if isinstance(ability.behaviors, list)
        for behavior in ability.behaviors
    )
    assert all(
        ability.damage_type is None or isinstance(ability.damage_type, DamageType)
        for ability in hero.abilities
    )
    assert all(isinstance(a, HeroAbility) for a in hero.innate_abilities)

    assert all(isinstance(talent, HeroTalent) for talent in hero.talents)
    assert all(talent.title != "" for talent in hero.talents)


def test_make_heroes_real_data_spot_checks():
    antimage = HEROES_BY_NAME["npc_dota_hero_antimage"]
    assert antimage.id == 1
    assert antimage.localized_name == "Anti-Mage"
    assert antimage.primary_attribute is HeroPrimaryAttribute.AGILITY
    assert antimage.attack_type is HeroAttackType.MELEE
    assert antimage.legs == 2
    assert antimage.captains_mode_enabled is True

    # A hero whose innate ability isn't the first entry in /constants/hero_abilities.
    persecutor = next(a for a in antimage.abilities if a.name == "antimage_persectur")
    assert persecutor.is_innate is True
    assert persecutor.title == "Persecutor"
    assert [a.name for a in antimage.innate_abilities] == ["antimage_persectur"]

    # Talent titles resolve through /constants/abilities, not just a humanized slug.
    hp_regen_talent = next(
        t for t in antimage.talents if t.name == "special_bonus_hp_regen_3"
    )
    assert hp_regen_talent.title == "+3 Health Regen"

    # Innate-ability cardinality varies per hero (§6): some heroes have none at all.
    tidehunter = HEROES_BY_NAME["npc_dota_hero_tidehunter"]
    assert tidehunter.innate_abilities == []


def test_make_heroes_observed_enum_values_match_known_real_data_universe():
    observed_primary_attrs = {hero.primary_attribute for hero in HEROES}
    observed_attack_types = {hero.attack_type for hero in HEROES}
    observed_roles = {role for hero in HEROES for role in hero.roles}
    observed_behaviors = {
        behavior
        for hero in HEROES
        for ability in hero.abilities
        if isinstance(ability.behaviors, list)
        for behavior in ability.behaviors
    }
    observed_damage_types = {
        ability.damage_type
        for hero in HEROES
        for ability in hero.abilities
        if ability.damage_type is not None
    }

    assert observed_primary_attrs == set(HeroPrimaryAttribute)
    assert observed_attack_types == set(HeroAttackType)
    assert observed_behaviors == set(AbilityBehavior)
    assert observed_damage_types == set(DamageType)
    # Not every role appears in current hero data (e.g. "Jungler" is effectively
    # retired), so only assert every observed role is a real, known HeroRole member.
    assert observed_roles <= set(HeroRole)
