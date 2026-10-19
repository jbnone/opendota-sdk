"""Regression sweep keeping `ItemName` in step with the vendored items fixture."""

import json
import re
from collections import Counter

import pytest

from opendota_sdk import ItemName

from .conftest import FIXTURES_DIR

REAL_ITEMS: dict[str, dict] = json.loads(
    (FIXTURES_DIR / "items.json").read_text(encoding="utf-8")
)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text.replace("'", "")).strip("_").upper()


_DISPLAY_SLUGS = Counter(
    _slug(item["dname"]) for item in REAL_ITEMS.values() if item.get("dname")
)


def _member_name(key: str, item: dict) -> str:
    """The naming rule `ItemName` follows.

    The in-game name, unless the item has none or another item shares it, in which
    case the internal name.
    """
    dname = item.get("dname")
    if dname and _DISPLAY_SLUGS[_slug(dname)] == 1:
        return _slug(dname)
    return _slug(key)


def test_every_fixture_item_has_exactly_one_member():
    enum_values = {member.value for member in ItemName}

    missing = sorted(set(REAL_ITEMS) - enum_values)
    stale = sorted(enum_values - set(REAL_ITEMS))

    assert not missing, (
        "items in the fixture with no ItemName member; add: "
        + ", ".join(
            f'{_member_name(key, REAL_ITEMS[key])} = "{key}"' for key in missing
        )
    )
    assert not stale, f"ItemName members with no item in the fixture: {stale}"
    assert len(ItemName) == len(REAL_ITEMS)


@pytest.mark.parametrize("key", list(REAL_ITEMS))
def test_member_follows_the_naming_rule(key):
    assert ItemName[_member_name(key, REAL_ITEMS[key])] == key


def test_tricky_names_follow_the_rule():
    assert ItemName.BLINK_DAGGER == "blink"
    assert ItemName.BLACK_KING_BAR == "black_king_bar"
    assert ItemName.BLACK_KING_BAR_RECIPE == "recipe_black_king_bar"
    assert ItemName.DAGON == "dagon"
    assert ItemName.DAGON_2 == "dagon_2"
    assert ItemName.RECIPE_WRAITH_PACT == "recipe_wraith_pact"


def test_members_are_plain_strings_equal_to_the_internal_name():
    for member in ItemName:
        assert isinstance(member, str)
        assert member == member.value
        assert hash(member) == hash(member.value)
