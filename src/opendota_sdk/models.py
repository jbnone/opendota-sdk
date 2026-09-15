"""Typed domain models for items, heroes, and hero statistics.

Every model here is a frozen dataclass assembled by the SDK from one or more OpenDota
payloads. Callers receive these instead of raw dictionaries; the original payload is
retained on `raw` for the top-level models (`Item`, `Hero`, `HeroStats`).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from opendota_sdk._context import active_client
from opendota_sdk.enums import (
    HeroAttackType,
    HeroPrimaryAttribute,
    HeroRole,
    HeroSkillBracket,
)


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
    """Damage type dealt by an item or ability effect."""

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
    """Which team an item's effect can target."""

    FRIENDLY = "Friendly"
    ENEMY = "Enemy"
    BOTH = "Both"


class ItemTargetType(str, Enum):
    """Which kind of unit an item's effect can target."""

    HERO = "Hero"
    BASIC = "Basic"
    TREE = "Tree"
    BUILDING = "Building"


@dataclass(frozen=True)
class ItemAbility:
    """An effect an item itself grants.

    Attributes:
        type: How the effect is triggered (active, passive, toggle, ...).
        title: Display name of the effect.
        description: Tooltip text describing the effect.
    """

    type: ItemAbilityType
    title: str
    description: str


@dataclass(frozen=True)
class Attribute:
    """A labeled key/value tooltip stat, shared by item and ability data.

    Attributes:
        key: Internal stat key (e.g. `"bonus_damage"`).
        value: Per-level values as strings. A single-element list means the stat is
            flat (no level scaling).
        display: Tooltip template for the stat, if the constants provide one.
        generated: Whether the tooltip entry was auto-generated rather than authored.
    """

    key: str
    value: list[str]
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
    """A Dota 2 item enriched with constants data.

    Built from `/constants/items`. Numeric fields that OpenDota reports as `false`
    when absent (`mana_cost`, `health_cost`, `cooldown`, `charges`) keep that
    `bool | int` shape: `False` means the item has no such cost.

    Attributes:
        id: Numeric item id.
        name: Internal item name (e.g. `"blink"`).
        image: Path to the item image, relative to the OpenDota CDN root.
        cost: Gold cost.
        created: Whether the item is a recipe-built item rather than a base purchase.
        mana_cost: Mana cost to use, or `False` if the item has none.
        health_cost: Health cost to use, or `False` if the item has none.
        cooldown: Cooldown in seconds, or `False` if the item has none.
        descriptive_name: Human-readable display name (e.g. `"Blink Dagger"`).
        lore: Flavor text.
        hints: Short usage hints shown in the shop tooltip.
        notes: Additional tooltip notes.
        description: Tooltip description.
        quality: Rarity classification, if known.
        damage_type: Damage type of the item's effect, if any.
        dispellable: Whether the item's effect can be dispelled, if known.
        target_team: Team the item's effect can target, if it targets anything.
        behaviors: Cast behaviors of the item's effect, or `False` if it has none.
        charges: Number of charges the item starts with, or `False` if not charge-based.
        black_king_bar_pierce: Whether the effect pierces Black King Bar's spell
            immunity; `None` when the constants do not say.
        tier: Neutral item tier (1-5), or `None` for non-neutral items.
        attributes: Tooltip stats granted by the item.
        abilities: Effects the item itself grants.
        target_types: Unit kinds the item's effect can target.
        components: Internal names of the items this one is built from.
        raw: The original merged payload this item was assembled from.
    """

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
    black_king_bar_pierce: bool | None = None
    tier: int | None = None

    attributes: list[Attribute] = field(default_factory=list)
    abilities: list[ItemAbility] = field(default_factory=list)
    target_types: list[ItemTargetType] = field(default_factory=list)
    components: list[str] = field(default_factory=list)

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        """Return a copy of the raw payload this item was assembled from.

        Returns:
            A shallow copy of `raw`, safe to mutate.
        """
        return dict(self.raw)


@dataclass(frozen=True)
class HeroTalent:
    """A hero talent-tree entry (level 10/15/20/25 choice).

    Attributes:
        name: Internal talent name (e.g. `"special_bonus_unique_antimage"`).
        level: Hero level at which the talent becomes available.
        title: Display text of the talent, resolved from `/constants/abilities`.
    """

    name: str
    level: int
    title: str = ""


@dataclass(frozen=True)
class HeroAbility:
    """A hero ability, resolved from `/constants/abilities` by name.

    Attributes:
        name: Internal ability name (e.g. `"antimage_blink"`).
        title: Display name.
        description: Tooltip description.
        behaviors: Cast behaviors, or `False` if the constants list none.
        damage_type: Damage type dealt, if any.
        attributes: Tooltip stats for the ability.
        is_innate: Whether the ability is innate (granted at level 1 without a skill point).
        mana_cost: Per-level mana cost. Empty means none; one value means flat (no level
            scaling); multiple values are ordered by ability level.
        cooldown: Per-level cooldown in seconds, with the same shape as `mana_cost`.
    """

    name: str
    title: str = ""
    description: str = ""
    behaviors: bool | list[AbilityBehavior] = False
    damage_type: DamageType | None = None
    attributes: list[Attribute] = field(default_factory=list)
    is_innate: bool = False
    mana_cost: list[float] = field(default_factory=list)
    cooldown: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class HeroBracketStats:
    """Pick/win counts for one hero in one skill bracket.

    Attributes:
        bracket: The rank bracket these counts belong to.
        picks: Number of matches the hero was picked in.
        wins: Number of those matches the hero won.
    """

    bracket: HeroSkillBracket
    picks: int
    wins: int

    @property
    def win_rate(self) -> float | None:
        """Wins as a fraction of picks.

        Returns:
            A value in `[0.0, 1.0]`, or `None` when the bracket has no picks (as is
            always the case for `HeroSkillBracket.IMMORTAL`, which OpenDota withholds).
        """
        return self.wins / self.picks if self.picks else None


@dataclass(frozen=True)
class HeroStats:
    """Live aggregate pick/win statistics for a hero, from `/heroStats`.

    Attributes:
        hero_id: Numeric hero id, matching `Hero.id`.
        hero_name: Internal hero name, matching `Hero.name`.
        brackets: Per-bracket pick/win counts, one entry per `HeroSkillBracket`.
        pub_picks: Total public-match picks across all brackets.
        pub_wins: Total public-match wins across all brackets.
        turbo_picks: Total Turbo-mode picks.
        turbo_wins: Total Turbo-mode wins.
        pro_picks: Total professional-match picks.
        pro_wins: Total professional-match wins.
        pro_bans: Total professional-match bans.
        pub_picks_trend: Public picks per day, most recent last.
        pub_wins_trend: Public wins per day, most recent last.
        turbo_picks_trend: Turbo picks per day, most recent last.
        turbo_wins_trend: Turbo wins per day, most recent last.
        raw: The original `/heroStats` entry this was assembled from.
    """

    hero_id: int
    hero_name: str

    brackets: list[HeroBracketStats] = field(default_factory=list)
    pub_picks: int = 0
    pub_wins: int = 0
    turbo_picks: int = 0
    turbo_wins: int = 0
    pro_picks: int = 0
    pro_wins: int = 0
    pro_bans: int = 0

    pub_picks_trend: list[int] = field(default_factory=list)
    pub_wins_trend: list[int] = field(default_factory=list)
    turbo_picks_trend: list[int] = field(default_factory=list)
    turbo_wins_trend: list[int] = field(default_factory=list)

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def pub_win_rate(self) -> float | None:
        """Public-match wins as a fraction of picks.

        Returns:
            A value in `[0.0, 1.0]`, or `None` when there are no public picks.
        """
        return self.pub_wins / self.pub_picks if self.pub_picks else None

    @property
    def turbo_win_rate(self) -> float | None:
        """Turbo-mode wins as a fraction of picks.

        Returns:
            A value in `[0.0, 1.0]`, or `None` when there are no Turbo picks.
        """
        return self.turbo_wins / self.turbo_picks if self.turbo_picks else None

    @property
    def pro_win_rate(self) -> float | None:
        """Professional-match wins as a fraction of picks.

        Returns:
            A value in `[0.0, 1.0]`, or `None` when there are no professional picks.
        """
        return self.pro_wins / self.pro_picks if self.pro_picks else None

    def as_dict(self) -> dict[str, Any]:
        """Return a copy of the raw `/heroStats` entry these stats were assembled from.

        Returns:
            A shallow copy of `raw`, safe to mutate.
        """
        return dict(self.raw)


@dataclass(frozen=True)
class Hero:
    """A Dota 2 hero enriched with constants, abilities, talents, and lore.

    Built by merging `/heroes` with `/constants/heroes`, `/constants/hero_abilities`,
    `/constants/abilities`, and `/constants/hero_lore`.

    Attributes:
        id: Numeric hero id.
        name: Internal hero name (e.g. `"npc_dota_hero_antimage"`).
        localized_name: Display name (e.g. `"Anti-Mage"`).
        primary_attribute: The stat that scales the hero's damage.
        attack_type: Whether the hero attacks at melee or ranged distance.
        roles: Suggested in-game roles.
        legs: Number of legs on the hero's model, used by the game engine for animation.
        image: Path to the hero portrait, relative to the OpenDota CDN root.
        icon: Path to the small hero icon, relative to the OpenDota CDN root.
        base_health: Base health before attribute bonuses.
        base_health_regen: Base health regeneration per second.
        base_mana: Base mana before attribute bonuses.
        base_mana_regen: Base mana regeneration per second.
        base_armor: Base armor before agility bonuses.
        base_magic_resistance: Base magic resistance percentage.
        base_attack_min: Minimum base attack damage.
        base_attack_max: Maximum base attack damage.
        base_attack_time: Base attack time (seconds between attacks at 0 attack speed).
        base_strength: Starting strength.
        base_agility: Starting agility.
        base_intelligence: Starting intelligence.
        strength_gain: Strength gained per level.
        agility_gain: Agility gained per level.
        intelligence_gain: Intelligence gained per level.
        attack_point: Delay in seconds between starting an attack and its damage landing.
        attack_range: Attack range in game units.
        projectile_speed: Attack projectile speed; `0` for melee heroes.
        attack_rate: Seconds between attacks at base attack speed.
        move_speed: Base movement speed.
        turn_rate: Degrees per second the hero can rotate, or `None` if not provided.
        captains_mode_enabled: Whether the hero is enabled in Captains Mode drafting.
        day_vision: Vision range during the day.
        night_vision: Vision range at night.
        abilities: The hero's abilities, including innate ones.
        talents: The hero's talent-tree entries.
        lore: Hero backstory.
        raw: The original merged payload this hero was assembled from.
    """

    id: int
    name: str
    localized_name: str
    primary_attribute: HeroPrimaryAttribute
    attack_type: HeroAttackType
    roles: list[HeroRole]
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
    attack_point: float
    attack_range: int
    projectile_speed: int
    attack_rate: float
    move_speed: int
    turn_rate: float | None
    captains_mode_enabled: bool
    day_vision: int
    night_vision: int

    abilities: list[HeroAbility] = field(default_factory=list)
    talents: list[HeroTalent] = field(default_factory=list)
    lore: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def innate_abilities(self) -> list[HeroAbility]:
        """The subset of `abilities` flagged as innate.

        Returns:
            Innate abilities in payload order. Most heroes have one, but the count varies.
        """
        return [ability for ability in self.abilities if ability.is_innate]

    async def get_stats(self) -> HeroStats | None:
        """Fetch this hero's live pick/win statistics via the active client.

        Delegates to `OpenDotaAsyncClient.get_hero_stat()` on the client bound to the
        current context, so it shares that client's cache: gathering `get_stats()` over
        every hero costs one HTTP request.

        Returns:
            The hero's statistics, or `None` if `/heroStats` has no entry for it.

        Raises:
            OpenDotaError: If no client is active, i.e. this is called outside
                `async with OpenDotaAsyncClient()` and without `client.activate()`.
        """
        return await active_client().get_hero_stat(hero_id=self.id)

    def as_dict(self) -> dict[str, Any]:
        """Return a copy of the raw merged payload this hero was assembled from.

        Returns:
            A shallow copy of `raw`, safe to mutate.
        """
        return dict(self.raw)
