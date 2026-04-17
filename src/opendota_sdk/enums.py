from enum import StrEnum


class HeroRole(StrEnum):
    CARRY = "Carry"
    SUPPORT = "Support"
    NUKER = "Nuker"
    DISABLER = "Disabler"
    JUNGLER = "Jungler"
    DURABLE = "Durable"
    ESCAPE = "Escape"
    Pusher = "Pusher"


class HeroAttackType(StrEnum):
    MELEE = "Melee"
    RANGED = "Ranged"


class HeroPrimaryAttr(StrEnum):
    STR = "str"
    AGI = "agi"
    INT = "int"
    ALL = "all"
