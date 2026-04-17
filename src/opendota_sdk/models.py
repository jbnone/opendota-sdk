from opendota_sdk.enums import HeroPrimaryAttr, HeroAttackType, HeroRole
from dataclasses import dataclass


@dataclass
class Hero:
    # Values coming from the API
    id: int
    name: str
    localized_name: str
    primary_attr: HeroPrimaryAttr
    attack_type: HeroAttackType
    roles: list[HeroRole]
    legs: int

    # Values coming from dotaconstants
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
