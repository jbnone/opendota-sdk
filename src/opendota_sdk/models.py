from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from opendota_sdk.enums import HeroAttackType, HeroPrimaryAttribute, HeroRole


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


@dataclass(frozen=True)
class ItemAbility:
    """An effect an item itself grants."""

    type: ItemAbilityType
    title: str
    description: str


@dataclass(frozen=True)
class Attribute:
    """A labeled key/value tooltip stat, shared by item and ability data."""

    key: str
    value: str | list[str]
    display: str | None = field(default=None)
    generated: bool = False


class AbilityBehavior(str, Enum):
    """How an ability casts, shared by item-granted and hero-innate abilities."""

    AREA_OF_EFFECT = "AOE"
    CHANNELED = "Channeled"
    HIDDEN = "Hidden"
    INSTANT_CAST = "Instant Cast"
    NO_TARGET = "No Target"
    PASSIVE = "Passive"
    POINT_TARGET = "Point Target"
    UNIT_TARGET = "Unit Target"


@dataclass(frozen=True)
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
    # Whether the item's effect pierces Black King Bar's spell-immunity.
    black_king_bar_pierce: bool | None = None
    tier: int | None = None

    attributes: list[Attribute] = field(default_factory=list)
    abilities: list[ItemAbility] = field(default_factory=list)
    target_types: list[ItemTargetType] = field(default_factory=list)
    components: list[str] = field(default_factory=list)

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(frozen=True)
class HeroTalent:
    """A hero talent-tree entry (level 10/15/20/25 choice)."""

    name: str
    level: int
    title: str = ""


@dataclass(frozen=True)
class HeroAbility:
    """A hero ability, resolved from /constants/abilities by name."""

    name: str
    title: str = ""
    description: str = ""
    behaviors: bool | list[AbilityBehavior] = False
    damage_type: DamageType | None = None
    attributes: list[Attribute] = field(default_factory=list)
    is_innate: bool = False
    # Per-level mana cost / cooldown (seconds). Empty means none; one value means flat
    # (no level scaling); multiple values are ordered by ability level.
    mana_cost: list[float] = field(default_factory=list)
    cooldown: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class Hero:
    """Dota 2 Hero enriched with constants, abilities, talents, and lore."""

    id: int
    name: str
    localized_name: str
    primary_attribute: HeroPrimaryAttribute
    attack_type: HeroAttackType
    roles: list[HeroRole]
    # Number of legs the hero's model has, used by the game engine for gait/animation.
    legs: int
    image: str
    icon: str
    base_health: int
    base_health_regen: float
    base_mana: int
    base_mana_regen: float
    base_armor: float
    base_magic_resistance: int
    base_attack_min: int
    base_attack_max: int
    base_attack_time: int
    base_strength: int
    base_agility: int
    base_intelligence: int
    strength_gain: float
    agility_gain: float
    intelligence_gain: float
    # Delay (in seconds) between starting an attack and its damage/effect landing.
    attack_point: float
    attack_range: int
    projectile_speed: int
    attack_rate: float
    move_speed: int
    # How many degrees per second the hero can rotate to face a new direction.
    turn_rate: float | None
    # Whether the hero is enabled in Captains Mode (the competitive draft format).
    captains_mode_enabled: bool
    day_vision: int
    night_vision: int

    abilities: list[HeroAbility] = field(default_factory=list)
    talents: list[HeroTalent] = field(default_factory=list)
    lore: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def innate_abilities(self) -> list[HeroAbility]:
        return [ability for ability in self.abilities if ability.is_innate]

    def as_dict(self) -> dict[str, Any]:
        return dict(self.raw)
