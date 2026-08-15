"""Regression sweep validating the assembler against every real item in items.json."""

import json

import pytest

from opendota_sdk.assembler import Assembler
from opendota_sdk.models import (
    DamageType,
    Dispellable,
    ItemAbilityType,
    ItemBehavior,
    ItemQuality,
    ItemTargetTeam,
    ItemTargetType,
)

from .conftest import FIXTURES_DIR

# Loaded at module scope (not a fixture) so item names are available for parametrize ids.
REAL_ITEMS: dict[str, dict] = json.loads(
    (FIXTURES_DIR / "items.json").read_text(encoding="utf-8")
)


def _normalize(name: str):
    return Assembler().normalize_item({**REAL_ITEMS[name], "name": name})


@pytest.mark.parametrize("name", list(REAL_ITEMS.keys()))
def test_assembler_normalizes_every_real_item_without_raising(name):
    item = _normalize(name)

    assert item.id >= 0
    assert isinstance(item.name, str)
    assert item.name != ""
    assert item.quality is None or isinstance(item.quality, ItemQuality)
    assert item.damage_type is None or isinstance(item.damage_type, DamageType)
    assert item.dispellable is None or isinstance(item.dispellable, Dispellable)
    assert isinstance(item.behaviors, bool) or all(
        isinstance(behavior, ItemBehavior) for behavior in item.behaviors
    )
    assert all(
        isinstance(target_type, ItemTargetType) for target_type in item.target_types
    )
    assert all(isinstance(ability.type, ItemAbilityType) for ability in item.abilities)


def test_assembler_real_data_spot_checks():
    blink = _normalize("blink")
    assert blink.id == 1
    assert blink.name == "blink"
    assert blink.descriptive_name == "Blink Dagger"

    recipe = _normalize("recipe_arcane_blink")
    assert recipe.quality is None
    assert recipe.abilities == []

    laning_item = _normalize("ward_dispenser")
    assert laning_item.quality is ItemQuality.CONSUMABLE_LANING

    both_target_item = _normalize("urn_of_shadows")
    assert both_target_item.target_team is ItemTargetTeam.BOTH

    strong_dispel_item = _normalize("sheepstick")
    assert strong_dispel_item.dispellable is Dispellable.STRONG_DISPELS_ONLY

    no_dname_item = _normalize("mechanical_arm")
    assert no_dname_item.name == "Mechanical Arm"
    assert no_dname_item.descriptive_name == ""


def test_assembler_observed_enum_values_match_known_real_data_universe():
    observed_qualities = set()
    observed_ability_types = set()
    observed_dispellables = set()

    for name in REAL_ITEMS:
        item = _normalize(name)
        if item.quality is not None:
            observed_qualities.add(item.quality)
        if item.dispellable is not None:
            observed_dispellables.add(item.dispellable)
        for ability in item.abilities:
            observed_ability_types.add(ability.type)

    assert observed_qualities == set(ItemQuality)
    assert observed_ability_types == set(ItemAbilityType)
    assert observed_dispellables == set(Dispellable)
