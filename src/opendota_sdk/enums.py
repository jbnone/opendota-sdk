"""Hero-related enumerations exposed on `Hero` and `HeroStats` models."""

from enum import IntEnum, StrEnum


class HeroSkillBracket(IntEnum):
    """Dota 2 rank medal tiers, used by OpenDota to bucket pick/win statistics.

    Values match the numeric prefixes of the `/heroStats` bracket keys (`1_pick`,
    `1_win`, ...). `IMMORTAL` is always reported as zero picks and wins, since OpenDota
    withholds that bracket from the public API.
    """

    HERALD = 1
    GUARDIAN = 2
    CRUSADER = 3
    ARCHON = 4
    LEGEND = 5
    ANCIENT = 6
    DIVINE = 7
    # OpenDota reports zeroes here; Immortal bracket data is withheld from the public API.
    IMMORTAL = 8


class HeroRole(StrEnum):
    """A hero's suggested in-game role(s), as classified by dotaconstants."""

    CARRY = "Carry"
    SUPPORT = "Support"
    NUKER = "Nuker"
    DISABLER = "Disabler"
    JUNGLER = "Jungler"
    DURABLE = "Durable"
    ESCAPE = "Escape"
    PUSHER = "Pusher"


class HeroAttackType(StrEnum):
    """Whether a hero attacks at melee or ranged distance."""

    MELEE = "Melee"
    RANGED = "Ranged"


class HeroPrimaryAttribute(StrEnum):
    """A hero's primary stat, which scales their damage output.

    `ALL` denotes universal heroes, whose damage scales with every attribute.
    """

    STRENGTH = "str"
    AGILITY = "agi"
    INTELLIGENCE = "int"
    ALL = "all"
