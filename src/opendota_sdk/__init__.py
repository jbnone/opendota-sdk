"""OpenDota SDK - A modern, domain-driven Python SDK for the OpenDota API."""

from importlib.metadata import version

from opendota_sdk._config import OpenDotaClientConfig, config_from_env, default_config
from opendota_sdk._errors import (
    HTTPStatusError,
    OpenDotaError,
    RateLimitError,
    ResponseDecodeError,
    TransportError,
)
from opendota_sdk.client import OpenDotaAsyncClient
from opendota_sdk.enums import HeroAttackType, HeroPrimaryAttribute, HeroRole
from opendota_sdk.models import (
    AbilityBehavior,
    Attribute,
    DamageType,
    Dispellable,
    Hero,
    HeroAbility,
    HeroTalent,
    Item,
    ItemAbility,
    ItemAbilityType,
    ItemQuality,
    ItemTargetTeam,
    ItemTargetType,
)

__version__ = version("opendota-sdk")
__all__ = [
    "AbilityBehavior",
    "Attribute",
    "DamageType",
    "Dispellable",
    "HTTPStatusError",
    "Hero",
    "HeroAbility",
    "HeroAttackType",
    "HeroPrimaryAttribute",
    "HeroRole",
    "HeroTalent",
    "Item",
    "ItemAbility",
    "ItemAbilityType",
    "ItemQuality",
    "ItemTargetTeam",
    "ItemTargetType",
    "OpenDotaAsyncClient",
    "OpenDotaClientConfig",
    "OpenDotaError",
    "RateLimitError",
    "ResponseDecodeError",
    "TransportError",
    "config_from_env",
    "default_config",
]
