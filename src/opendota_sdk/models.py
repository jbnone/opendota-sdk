from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from opendota_sdk.enums import HeroAttackType, HeroPrimaryAttr, HeroRole


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
class Attribute:
    """A labeled key/value tooltip stat, shared by item and ability data."""

    key: str
    value: str | list[str]
    display: str | None = field(default=None)
    generated: bool = False


class AbilityBehavior(str, Enum):
    """How an ability casts, shared by item-granted and hero-innate abilities."""

    AOE = "AOE"
    CHANNELED = "Channeled"
    HIDDEN = "Hidden"
    INSTANT_CAST = "Instant Cast"
    NO_TARGET = "No Target"
    PASSIVE = "Passive"
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
    behaviors: bool | list[AbilityBehavior] = False

    charges: bool | int = False
    bkb_pierce: bool | None = None
    tier: int | None = None

    attributes: list[Attribute] = field(default_factory=list)
    abilities: list[ItemAbility] = field(default_factory=list)
    target_types: list[ItemTargetType] = field(default_factory=list)
    components: list[str] = field(default_factory=list)

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass
class HeroTalent:
    """A hero talent-tree entry (level 10/15/20/25 choice)."""

    name: str
    level: int
    title: str = ""


@dataclass
class HeroAbility:
    """A hero ability, resolved from /constants/abilities by name."""

    name: str
    title: str = ""
    description: str = ""
    behaviors: bool | list[AbilityBehavior] = False
    damage_type: DamageType | None = None
    attributes: list[Attribute] = field(default_factory=list)
    is_innate: bool = False


@dataclass
class Hero:
    id: int
    name: str
    localized_name: str
    primary_attr: HeroPrimaryAttr
    attack_type: HeroAttackType
    roles: list[HeroRole]
    legs: int
    img: str
    icon: str
    base_health: int
    base_health_regen: float
    base_mana: int
    base_mana_regen: float
    base_armor: float
    base_mr: int
    base_attack_min: int
    base_attack_max: int
    base_attack_time: int
    base_str: int
    base_agi: int
    base_int: int
    str_gain: float
    agi_gain: float
    int_gain: float
    attack_point: float
    attack_range: int
    projectile_speed: int
    attack_rate: float
    move_speed: int
    turn_rate: float | None
    cm_enabled: bool
    day_vision: int
    night_vision: int

    abilities: list[HeroAbility] = field(default_factory=list)
    talents: list[HeroTalent] = field(default_factory=list)
    lore: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def innate_abilities(self) -> list[HeroAbility]:
        return [ability for ability in self.abilities if ability.is_innate]
