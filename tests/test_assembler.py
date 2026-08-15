"""Tests for item record parsing and item assembly."""

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
