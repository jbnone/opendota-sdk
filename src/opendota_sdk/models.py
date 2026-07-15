from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ItemQuality(str, Enum):
    """Item quality/rarity classification."""

    ARTIFACT = "artifact"
    COMMON = "common"
    COMPONENT = "component"
    CONSUMABLE = "consumable"
    CONSUMABLE_LANING = "consumable;laning"
    EPIC = "epic"
    RARE = "rare"
    SECRET_SHOP = "secret_shop"


class DamageType(str, Enum):
    """Damage type for item effects."""

    MAGICAL = "Magical"
    PHYSICAL = "Physical"


class Dispellable(str, Enum):
    """Whether an item effect can be dispelled."""

    YES = "Yes"
    NO = "No"
    STRONG_DISPELS_ONLY = "Strong Dispels Only"


class ItemAbilityType(str, Enum):
    """Classification of item abilities."""

    ACTIVE = "active"
    PASSIVE = "passive"
    USE = "use"
    UPGRADE = "upgrade"
    TOGGLE = "toggle"


class ItemTargetTeam(str, Enum):
    """Classification of item's target team."""

    FRIENDLY = "Friendly"
    ENEMY = "Enemy"
    BOTH = "Both"


class ItemTargetType(str, Enum):
    """Classification of item's target type."""

    HERO = "Hero"
    BASIC = "Basic"
    TREE = "Tree"
    BUILDING = "Building"


@dataclass
class ItemAbility:
    type: ItemAbilityType
    title: str
    description: str


@dataclass
class ItemAttribute:
    key: str
    value: str
    display: str | None = field(default=None)


class ItemBehavior(str, Enum):
    AOE = "AOE"
    CHANNELED = "Channeled"
    INSTANT_CAST = "Instant Cast"
    NO_TARGET = "No Target"
    POINT_TARGET = "Point Target"
    UNIT_TARGET = "Unit Target"


@dataclass
class Item:
    """Dota 2 Item enriched with constants data."""

    id: int
    name: str
    image: str
    cost: int
    created: bool
    mana_cost: bool | int
    health_cost: bool | int
    cooldown: bool | int

    descriptive_name: str = ""
    lore: str = ""
    hints: list[str] = field(default_factory=list)
    notes: str = ""
    description: str = ""

    quality: ItemQuality | None = None
    damage_type: DamageType | None = None
    dispellable: Dispellable | None = None
    target_team: ItemTargetTeam | None = None
    behaviors: bool | list[ItemBehavior] = False

    charges: bool | int = False
    bkb_pierce: bool | None = None
    tier: int | None = None

    attributes: list[ItemAttribute] = field(default_factory=list)
    abilities: list[ItemAbility] = field(default_factory=list)
    target_types: list[ItemTargetType] = field(default_factory=list)
    components: list[str] = field(default_factory=list)

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.raw)
