from enum import IntEnum, StrEnum


class HeroSkillBracket(IntEnum):
    """Dota 2 rank medal tiers, used by OpenDota to bucket pick/win statistics."""

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
    """A hero's primary stat, which scales their damage output."""

    STRENGTH = "str"
    AGILITY = "agi"
    INTELLIGENCE = "int"
    ALL = "all"
