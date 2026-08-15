"""Tests for item record parsing and item assembly."""

import pytest

from opendota_sdk._records import ItemRecord
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


def test_item_record_from_raw_preserves_aliases_and_raw_payload():
    raw = {
        "id": "42",
        "dname": "Arcane Blink",
        "img": "/apps/dota2/images/items/arcane_blink_png.png",
        "mc": "25",
        "hc": "0",
        "cd": "7",
        "bkb_pierce": "yes",
        "description": "Teleport with arcane power.",
    }

    record = ItemRecord.from_raw(raw)

    assert record.id == 42
    assert record.name == "Arcane Blink"
    assert record.dname == "Arcane Blink"
    assert record.mc == "25"
    assert record.hc == "0"
    assert record.cd == "7"
    assert record.bkbpierce == "yes"
    assert record.desc == "Teleport with arcane power."
    assert record.raw == raw


def test_normalize_item_builds_typed_item_from_raw_payload():
    raw = {
        "id": "1",
        "name": "blink",
        "dname": "Blink Dagger",
        "img": "/apps/dota2/images/items/blink_png.png",
        "cost": "2250",
        "created": "yes",
        "mc": "0",
        "hc": "false",
        "cd": "15",
        "hint": ["Blink to a target point."],
        "notes": "Disabled by recent damage.",
        "desc": "Short distance teleport.",
        "qual": "component",
        "dmg_type": "Magical",
        "dispellable": "No",
        "target_team": ["Friendly"],
        "behavior": "Point Target, Instant Cast",
        "charges": "0",
        "bkbpierce": "no",
        "tier": "1",
        "attrib": [{"key": "blink_range", "value": "1200", "display": "range"}],
        "abilities": [
            {
                "type": "active",
                "title": "Blink",
                "description": "Teleport to a target point.",
            },
            {
                "type": "invalid",
                "title": "Ignored",
                "description": "Should not be included.",
            },
        ],
        "target_type": ["Hero", "Tree", "Unknown"],
        "components": ["staff_of_wizardry", None],
    }

    item = Assembler().normalize_item(raw)

    assert item.id == 1
    assert item.name == "blink"
    assert item.descriptive_name == "Blink Dagger"
    assert item.cost == 2250
    assert item.created is True
    assert item.mana_cost == 0
    assert item.health_cost is False
    assert item.cooldown == 15
    assert item.description == "Short distance teleport."
    assert item.notes == "Disabled by recent damage."
    assert item.hints == ["Blink to a target point."]
    assert item.quality is ItemQuality.COMPONENT
    assert item.damage_type is DamageType.MAGICAL
    assert item.dispellable is Dispellable.NO
    assert item.target_team is ItemTargetTeam.FRIENDLY
    assert item.behaviors == [ItemBehavior.POINT_TARGET, ItemBehavior.INSTANT_CAST]
    assert item.charges == 0
    assert item.bkb_pierce is False
    assert item.tier == 1
    assert item.attributes[0].key == "blink_range"
    assert item.attributes[0].value == "1200"
    assert len(item.abilities) == 1
    assert item.abilities[0].type is ItemAbilityType.ACTIVE
    assert item.target_types == [ItemTargetType.HERO, ItemTargetType.TREE]
    assert item.components == ["staff_of_wizardry"]
    assert item.raw == raw


def test_normalize_item_defaults_missing_or_unknown_values():
    item = Assembler().normalize_item(
        {
            "id": None,
            "name": None,
            "cost": None,
            "created": None,
            "mc": "unknown",
            "behavior": ["Unknown"],
            "qual": "unknown",
            "target_team": ["Unknown"],
        }
    )

    assert item.id == 0
    assert item.name == ""
    assert item.cost == 0
    assert item.created is False
    assert item.mana_cost is False
    assert item.behaviors is False
    assert item.quality is None
    assert item.target_team is None


# --- Phase A: ItemRecord.from_raw --------------------------------------------------


def test_item_record_alias_precedence_primary_key_wins_when_both_present():
    raw = {
        "id": 1,
        "mc": "10",
        "mana_cost": "999",
        "hc": "5",
        "health_cost": "999",
        "cd": "3",
        "cooldown": "999",
        "bkb_pierce": "yes",
        "bkbpierce": "no",
        "desc": "primary desc",
        "description": "fallback desc",
    }

    record = ItemRecord.from_raw(raw)

    assert record.mc == "10"
    assert record.hc == "5"
    assert record.cd == "3"
    assert record.bkbpierce == "yes"
    assert record.desc == "primary desc"


def test_item_record_alias_fallback_key_used_when_primary_absent():
    raw = {
        "id": 1,
        "mana_cost": "999",
        "health_cost": "888",
        "cooldown": "777",
        "bkbpierce": "no",
        "description": "fallback desc",
    }

    record = ItemRecord.from_raw(raw)

    assert record.mc == "999"
    assert record.hc == "888"
    assert record.cd == "777"
    assert record.bkbpierce == "no"
    assert record.desc == "fallback desc"


def test_item_record_name_fallback_chain():
    both_present = ItemRecord.from_raw(
        {"id": 1, "name": "blink", "dname": "Blink Dagger"}
    )
    assert both_present.name == "blink"

    only_dname = ItemRecord.from_raw({"id": 1, "dname": "Blink Dagger"})
    assert only_dname.name == "Blink Dagger"

    neither = ItemRecord.from_raw({"id": 1})
    assert neither.name == ""


@pytest.mark.parametrize("raw_id", [None, 0, ""])
def test_item_record_id_defaults_to_zero_for_falsy_values(raw_id):
    record = ItemRecord.from_raw({"id": raw_id})
    assert record.id == 0


def test_item_record_id_missing_key_defaults_to_zero():
    assert ItemRecord.from_raw({}).id == 0


def test_item_record_raw_is_an_independent_copy():
    raw = {"id": 1, "name": "blink"}
    record = ItemRecord.from_raw(raw)

    raw["name"] = "mutated"

    assert record.raw["name"] == "blink"


def test_item_record_from_raw_all_defaults():
    record = ItemRecord.from_raw({})

    assert record.id == 0
    assert record.name == ""
    assert record.dname == ""
    assert record.img == ""
    assert record.cost is None
    assert record.created is None
    assert record.mc is None
    assert record.hc is None
    assert record.cd is None
    assert record.charges is None
    assert record.components is None
    assert record.attrib is None
    assert record.abilities is None
    assert record.behavior is None
    assert record.hint is None
    assert record.qual is None
    assert record.dmg_type is None
    assert record.dispellable is None
    assert record.target_team is None
    assert record.target_type is None
    assert record.tier is None
    assert record.bkbpierce is None
    assert record.desc is None
    assert record.notes is None
    assert record.lore is None
    assert record.raw == {}


def test_item_record_recipe_shaped_payload_has_no_qual_or_abilities():
    # Real dotaconstants entry (recipe_arcane_blink): recipes omit qual/abilities entirely.
    raw = {
        "id": 606,
        "img": "/apps/dota2/images/dota_react/items/recipe.png?t=1593393829403",
        "dname": "Arcane Blink Recipe",
        "cost": 1750,
        "behavior": False,
        "notes": "",
        "attrib": [],
        "mc": False,
        "hc": False,
        "cd": False,
        "lore": "",
        "components": None,
        "created": False,
        "charges": False,
    }

    record = ItemRecord.from_raw(raw)

    assert record.qual is None
    assert record.abilities is None


# --- Phase B: Assembler private normalization helpers -------------------------------


@pytest.mark.parametrize("value", [True, False])
def test_normalize_bool_passthrough_for_bools(value):
    assert Assembler()._normalize_bool(value) is value


@pytest.mark.parametrize("value", ["yes", "true", "1", "YES", " True "])
def test_normalize_bool_truthy_strings(value):
    assert Assembler()._normalize_bool(value) is True


@pytest.mark.parametrize("value", ["no", "false", "0", "NO", " False "])
def test_normalize_bool_falsy_strings(value):
    assert Assembler()._normalize_bool(value) is False


@pytest.mark.parametrize(
    "value,expected", [(1, True), (0, False), (2.0, True), (0.0, False)]
)
def test_normalize_bool_numeric_values(value, expected):
    assert Assembler()._normalize_bool(value) is expected


def test_normalize_bool_unrecognized_string_and_none_return_default():
    assembler = Assembler()
    assert assembler._normalize_bool("maybe") is None
    assert assembler._normalize_bool("maybe", default=False) is False
    assert assembler._normalize_bool(None) is None
    assert assembler._normalize_bool(None, default=True) is True


def test_normalize_int_none_returns_default():
    assert Assembler()._normalize_int(None) is None
    assert Assembler()._normalize_int(None, default=7) == 7


def test_normalize_int_passthrough_and_coercion():
    assembler = Assembler()
    assert assembler._normalize_int(5) == 5
    assert assembler._normalize_int(3.9) == 3
    assert assembler._normalize_int("42") == 42
    assert assembler._normalize_int("  42  ") == 42
    assert assembler._normalize_int("not a number") is None
    assert assembler._normalize_int("not a number", default=-1) == -1


def test_normalize_bool_or_int_checks_bool_before_int():
    assembler = Assembler()
    assert assembler._normalize_bool_or_int(True) is True
    assert assembler._normalize_bool_or_int(False) is False
    assert assembler._normalize_bool_or_int(5) == 5
    assert assembler._normalize_bool_or_int(5.0) == 5
    assert assembler._normalize_bool_or_int("yes") is True
    assert assembler._normalize_bool_or_int("no") is False
    assert assembler._normalize_bool_or_int("10") == 10
    assert assembler._normalize_bool_or_int("garbage") is None
    assert assembler._normalize_bool_or_int("garbage", default=False) is False


def test_normalize_str_none_passthrough_and_coercion():
    assembler = Assembler()
    assert assembler._normalize_str(None) is None
    assert assembler._normalize_str("blink") == "blink"
    assert assembler._normalize_str(42) == "42"
    assert assembler._normalize_str(True) == "True"


def test_normalize_enum_exact_match_list_and_invalid():
    assembler = Assembler()
    assert assembler._normalize_enum("Yes", Dispellable) is Dispellable.YES
    assert assembler._normalize_enum(["Unknown", "Yes"], Dispellable) is Dispellable.YES
    assert assembler._normalize_enum(["Unknown", "Also Unknown"], Dispellable) is None
    assert assembler._normalize_enum("Unknown", Dispellable) is None
    assert assembler._normalize_enum(None, Dispellable) is None


def test_normalize_str_list_variants():
    assembler = Assembler()
    assert assembler._normalize_str_list(None) == []
    assert assembler._normalize_str_list(["a", None, "b"]) == ["a", "b"]
    assert assembler._normalize_str_list("Friendly") == ["Friendly"]


def test_normalize_dict_list_filters_non_dict_entries():
    assembler = Assembler()
    assert assembler._normalize_dict_list("not a list") == []
    assert assembler._normalize_dict_list(
        [{"key": "a"}, "not a dict", {"key": "b"}]
    ) == [
        {"key": "a"},
        {"key": "b"},
    ]


def test_normalize_attributes_defaults_missing_fields():
    attributes = Assembler()._normalize_attributes(
        [{"value": "10"}, {"key": "range", "value": "1200", "display": "Range"}]
    )

    assert attributes[0].key == ""
    assert attributes[0].value == "10"
    assert attributes[0].display is None
    assert attributes[1].display == "Range"


def test_normalize_abilities_covers_all_real_ability_types():
    # active/passive/use/upgrade/toggle are all observed in items.json (e.g. rapier's "toggle").
    raw_abilities = [
        {"type": "active", "title": "A", "description": "a"},
        {"type": "passive", "title": "P", "description": "p"},
        {"type": "use", "title": "U", "description": "u"},
        {"type": "upgrade", "title": "Up", "description": "up"},
        {"type": "toggle", "title": "T", "description": "t"},
        {"type": "invalid", "title": "Bad", "description": "bad"},
        {"title": "Missing Type"},
    ]

    abilities = Assembler()._normalize_abilities(raw_abilities)

    assert [ability.type for ability in abilities] == [
        ItemAbilityType.ACTIVE,
        ItemAbilityType.PASSIVE,
        ItemAbilityType.USE,
        ItemAbilityType.UPGRADE,
        ItemAbilityType.TOGGLE,
    ]


def test_normalize_abilities_defaults_missing_title_and_description():
    abilities = Assembler()._normalize_abilities([{"type": "active"}])
    assert abilities[0].title == ""
    assert abilities[0].description == ""


def test_normalize_behaviors_bool_passthrough():
    assembler = Assembler()
    assert assembler._normalize_behaviors(True) is True
    assert assembler._normalize_behaviors(False) is False


def test_normalize_behaviors_single_string():
    assert Assembler()._normalize_behaviors("Point Target") == [
        ItemBehavior.POINT_TARGET
    ]


def test_normalize_behaviors_comma_separated_string():
    behaviors = Assembler()._normalize_behaviors("Point Target, Instant Cast")
    assert behaviors == [ItemBehavior.POINT_TARGET, ItemBehavior.INSTANT_CAST]


def test_normalize_behaviors_real_data_list_of_strings():
    # Real shape (e.g. faerie_fire): behavior as a JSON list of strings, not a comma string.
    behaviors = Assembler()._normalize_behaviors(["Instant Cast", "No Target"])
    assert behaviors == [ItemBehavior.INSTANT_CAST, ItemBehavior.NO_TARGET]


def test_normalize_behaviors_empty_list_falls_back_to_false():
    assert Assembler()._normalize_behaviors([]) is False


def test_normalize_target_team_bare_string():
    assert Assembler()._normalize_target_team("Friendly") is ItemTargetTeam.FRIENDLY


def test_normalize_target_team_real_two_element_list_uses_first_entry_only():
    # Real value from ethereal_blade: only "Enemy" is captured, "Friendly" is silently dropped.
    assert (
        Assembler()._normalize_target_team(["Enemy", "Friendly"])
        is ItemTargetTeam.ENEMY
    )


def test_normalize_target_team_empty_list_returns_none():
    assert Assembler()._normalize_target_team([]) is None


def test_normalize_target_team_both_literal_value():
    assert Assembler()._normalize_target_team("Both") is ItemTargetTeam.BOTH


def test_normalize_target_types_bare_string():
    assert Assembler()._normalize_target_types("Hero") == [ItemTargetType.HERO]


def test_normalize_target_types_empty_list():
    assert Assembler()._normalize_target_types([]) == []


def test_normalize_components_none_and_filters_none_entries():
    assembler = Assembler()
    assert assembler._normalize_components(None) == []
    assert assembler._normalize_components(["blink", None, "reaver"]) == [
        "blink",
        "reaver",
    ]


def test_normalize_components_preserves_literal_empty_string_entries():
    # Real items (pipe, urn_of_shadows, hydras_breath) have a literal "" entry;
    # only None is filtered, "" passes through as documented current behavior.
    assert Assembler()._normalize_components(["ring_of_tarrasque", "cloak", ""]) == [
        "ring_of_tarrasque",
        "cloak",
        "",
    ]


# --- Phase C: Assembler.normalize_item end-to-end contract --------------------------


def test_normalize_item_recipe_shaped_payload_defaults():
    raw = {
        "id": 606,
        "name": "recipe_arcane_blink",
        "dname": "Arcane Blink Recipe",
        "cost": 1750,
        "behavior": False,
        "notes": "",
        "attrib": [],
        "mc": False,
        "hc": False,
        "cd": False,
        "lore": "",
        "components": None,
        "created": False,
        "charges": False,
    }

    item = Assembler().normalize_item(raw)

    assert item.quality is None
    assert item.abilities == []
    assert item.behaviors is False
    assert item.components == []


def test_normalize_item_handles_keys_missing_entirely_not_just_null():
    # recipe_iron_talon-shaped: hc and charges keys are entirely absent, not explicit null.
    raw = {
        "id": 238,
        "name": "recipe_iron_talon",
        "dname": "Iron Talon Recipe",
        "cost": 125,
        "desc": "",
        "notes": "",
        "attrib": [],
        "mc": False,
        "cd": False,
        "lore": "",
        "components": None,
        "created": False,
    }

    item = Assembler().normalize_item(raw)

    assert item.health_cost is False
    assert item.charges is False


def test_normalize_item_neutral_token_null_cost_and_absent_quality():
    raw = {
        "id": 2091,
        "name": "tier1_token",
        "dname": "Tier 1 Token",
        "cost": None,
        "behavior": "No Target",
        "notes": "",
        "attrib": [],
        "mc": False,
        "hc": False,
        "cd": False,
        "lore": "",
        "components": None,
        "created": False,
        "charges": False,
    }

    item = Assembler().normalize_item(raw)

    assert item.cost == 0
    assert item.quality is None


@pytest.mark.parametrize(
    "name,expected",
    [
        ("mechanical_arm", "Mechanical Arm"),
        ("horizon", "Horizon"),
        ("greater_mango", "Greater Mango"),
        ("super_blink", "Super Blink"),
        ("miniboss_minion_summoner", "Miniboss Minion Summoner"),
    ],
)
def test_normalize_item_humanizes_name_when_dname_is_absent(name, expected):
    item = Assembler().normalize_item({"id": 1, "name": name, "cost": 0})

    assert item.name == expected
    assert item.descriptive_name == ""


def test_normalize_item_name_unaffected_when_dname_present():
    item = Assembler().normalize_item(
        {"id": 1, "name": "blink", "dname": "Blink Dagger", "cost": 2250}
    )

    assert item.name == "blink"
    assert item.descriptive_name == "Blink Dagger"


def test_normalize_item_consumable_laning_quality():
    item = Assembler().normalize_item(
        {"id": 218, "name": "ward_dispenser", "qual": "consumable;laning", "cost": 50}
    )

    assert item.quality is ItemQuality.CONSUMABLE_LANING


def test_normalize_item_target_team_and_target_type_as_bare_strings():
    item = Assembler().normalize_item(
        {
            "id": 4,
            "name": "chainmail",
            "dname": "Chainmail",
            "target_team": "Friendly",
            "target_type": "Hero",
            "cost": 500,
        }
    )

    assert item.target_team is ItemTargetTeam.FRIENDLY
    assert item.target_types == [ItemTargetType.HERO]


def test_normalize_item_target_type_multi_value_list_retains_order():
    item = Assembler().normalize_item(
        {
            "id": 1123,
            "name": "blood_grenade",
            "dname": "Blood Grenade",
            "target_team": "Enemy",
            "target_type": ["Hero", "Basic"],
            "cost": 50,
        }
    )

    assert item.target_types == [ItemTargetType.HERO, ItemTargetType.BASIC]


def test_normalize_item_strong_dispels_only():
    item = Assembler().normalize_item(
        {
            "id": 96,
            "name": "sheepstick",
            "dname": "Scythe of Vyse",
            "dispellable": "Strong Dispels Only",
            "cost": 5200,
        }
    )

    assert item.dispellable is Dispellable.STRONG_DISPELS_ONLY


@pytest.mark.parametrize("quality_value", [quality.value for quality in ItemQuality])
def test_normalize_item_resolves_every_item_quality_enum_value(quality_value):
    item = Assembler().normalize_item(
        {
            "id": 1,
            "name": "test_item",
            "dname": "Test Item",
            "qual": quality_value,
            "cost": 0,
        }
    )

    assert item.quality is ItemQuality(quality_value)


def test_item_raw_excluded_from_equality_and_repr():
    base = {"id": 1, "name": "blink", "dname": "Blink Dagger", "cost": 2250}
    item_a = Assembler().normalize_item({**base, "raw_marker": "a"})
    item_b = Assembler().normalize_item({**base, "raw_marker": "b"})

    assert item_a == item_b
    assert "raw=" not in repr(item_a)


def test_item_as_dict_returns_a_copy_of_raw():
    item = Assembler().normalize_item(
        {"id": 1, "name": "blink", "dname": "Blink Dagger", "cost": 2250}
    )

    as_dict = item.as_dict()
    as_dict["mutated"] = True

    assert "mutated" not in item.raw


def test_normalize_record_delegates_to_item_record_from_raw():
    raw = {"id": 1, "name": "blink"}
    assert Assembler().normalize_record(raw) == ItemRecord.from_raw(raw)


def test_list_items_preserves_order_and_count_for_mixed_input():
    assembler = Assembler()
    raw_dict = {"id": 1, "name": "blink", "dname": "Blink Dagger"}
    raw_record = ItemRecord.from_raw({"id": 2, "name": "reaver", "dname": "Reaver"})

    items = assembler.list_items([raw_dict, raw_record])

    assert [item.id for item in items] == [1, 2]
    assert [item.name for item in items] == ["blink", "reaver"]


def test_get_item_is_equivalent_to_normalize_item():
    assembler = Assembler()
    raw = {"id": 1, "name": "blink", "dname": "Blink Dagger"}

    assert assembler.get_item(raw) == assembler.normalize_item(raw)


def test_normalize_item_accepts_pre_built_item_record_directly():
    record = ItemRecord(id=99, name="custom", dname="Custom Item", raw={"custom": True})

    item = Assembler().normalize_item(record)

    assert item.id == 99
    assert item.descriptive_name == "Custom Item"
    assert item.raw == {"custom": True}
