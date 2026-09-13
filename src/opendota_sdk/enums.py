from enum import StrEnum


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
