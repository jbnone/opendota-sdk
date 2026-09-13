"""Model assembler that builds domain models from raw constants payloads."""

from collections.abc import Sequence
from enum import Enum
from typing import Any, TypeVar

from opendota_sdk._errors import OpenDotaError
from opendota_sdk._records import ItemRecord
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

E = TypeVar("E", bound=Enum)


class Assembler:
    """Generic assembler with reusable normalization helpers."""

    def normalize_item(self, raw: dict[str, Any] | ItemRecord) -> Item:
        """Build an Item model from raw item payload or an ItemRecord."""
        if isinstance(raw, ItemRecord):
            record = raw
        else:
            record = ItemRecord.from_raw(raw)

        descriptive_name = self._normalize_str(record.dname) or ""
        name = self._normalize_str(record.name) or descriptive_name or ""
        if not descriptive_name:
            # dotaconstants omits dname for some items; humanize the slug instead of exposing it raw.
            name = self._humanize_slug(name)

        return Item(
            id=self._require_int(record.id),
            name=name,
            image=self._normalize_str(record.img) or "",
            cost=self._require_int(record.cost),
            created=self._require_bool(record.created),
            mana_cost=self._require_bool_or_int(record.mc),
            health_cost=self._require_bool_or_int(record.hc),
            cooldown=self._require_bool_or_int(record.cd),
            descriptive_name=descriptive_name,
            lore=self._normalize_str(record.lore) or "",
            hints=self._normalize_str_list(record.hint),
            notes=self._normalize_str(record.notes) or "",
            description=self._normalize_str(record.desc) or "",
            quality=self._normalize_enum(record.qual, ItemQuality),
            damage_type=self._normalize_enum(record.dmg_type, DamageType),
            dispellable=self._normalize_enum(record.dispellable, Dispellable),
            target_team=self._normalize_target_team(record.target_team),
            behaviors=self._normalize_behaviors(record.behavior),
            charges=self._require_bool_or_int(record.charges),
            black_king_bar_pierce=self._normalize_bool(record.bkbpierce),
            tier=self._normalize_int(record.tier),
            attributes=self._normalize_attributes(record.attrib),
            abilities=self._normalize_abilities(record.abilities),
            target_types=self._normalize_target_types(record.target_type),
            components=self._normalize_components(record.components),
            raw=record.raw,
        )

    def normalize_record(self, raw: dict[str, Any]) -> ItemRecord:
        """Build an ItemRecord from raw payload."""
        return ItemRecord.from_raw(raw)

    def list_items(
        self, raw_items: Sequence[dict[str, Any] | ItemRecord]
    ) -> list[Item]:
        """Build Item models from raw payloads."""
        return [self.normalize_item(raw) for raw in raw_items]

    def get_item(self, raw_item: dict[str, Any] | ItemRecord) -> Item:
        """Build a single Item model from a raw payload."""
        return self.normalize_item(raw_item)

    def normalize_hero_ability(
        self, name: str, raw: dict[str, Any] | None
    ) -> HeroAbility:
        """Build a HeroAbility from a /constants/abilities entry (or a name-only stub if not found)."""
        if raw is None:
            return HeroAbility(name=name, title=self._humanize_slug(name))

        title = self._normalize_str(raw.get("dname")) or self._humanize_slug(name)
        return HeroAbility(
            name=name,
            title=title,
            description=self._normalize_str(raw.get("desc")) or "",
            behaviors=self._normalize_behaviors(raw.get("behavior")),
            damage_type=self._normalize_enum(raw.get("dmg_type"), DamageType),
            attributes=self._normalize_attributes(raw.get("attrib")),
            is_innate=raw.get("is_innate") is True,
            mana_cost=self._normalize_float_list(raw.get("mc")),
            cooldown=self._normalize_float_list(raw.get("cd")),
        )

    def normalize_hero_talent(
        self,
        raw: dict[str, Any],
        *,
        abilities_by_name: dict[str, dict[str, Any]] | None = None,
    ) -> HeroTalent:
        """Build a HeroTalent from a hero_abilities.json talent entry."""
        name = self._normalize_str(raw.get("name")) or ""
        talent_data = (abilities_by_name or {}).get(name)
        title = self._humanize_slug(name)
        if talent_data is not None:
            title = self._normalize_str(talent_data.get("dname")) or title
        return HeroTalent(
            name=name,
            level=self._require_int(raw.get("level")),
            title=title,
        )

    def _flatten_ability_names(self, value: Any) -> list[str]:
        """Flatten one level of nesting (e.g. Monkey King's transform-state pair)."""
        if not isinstance(value, list):
            return []
        names: list[str] = []
        for entry in value:
            if isinstance(entry, list):
                names.extend(str(item) for item in entry)
            else:
                names.append(str(entry))
        return names

    def normalize_hero(
        self,
        merged: dict[str, Any],
        *,
        abilities_by_name: dict[str, dict[str, Any]] | None = None,
    ) -> Hero:
        """Build a Hero model from a merged /heroes + /constants/heroes payload."""
        hero_id = self._normalize_int(merged.get("id"))
        name = self._normalize_str(merged.get("name"))
        localized_name = self._normalize_str(merged.get("localized_name"))
        primary_attribute = self._normalize_enum(
            merged.get("primary_attr"), HeroPrimaryAttribute
        )
        attack_type = self._normalize_enum(merged.get("attack_type"), HeroAttackType)
        if (
            hero_id is None
            or not name
            or not localized_name
            or primary_attribute is None
            or attack_type is None
        ):
            raise OpenDotaError(
                "Cannot build Hero: missing or malformed id/name/localized_name/"
                f"primary_attr/attack_type in payload {merged!r}"
            )

        abilities_by_name = abilities_by_name or {}
        abilities = [
            self.normalize_hero_ability(
                ability_name, abilities_by_name.get(ability_name)
            )
            for ability_name in self._flatten_ability_names(merged.get("abilities"))
        ]
        talents = [
            self.normalize_hero_talent(entry, abilities_by_name=abilities_by_name)
            for entry in self._normalize_dict_list(merged.get("talents"))
        ]

        return Hero(
            id=hero_id,
            name=name,
            localized_name=localized_name,
            primary_attribute=primary_attribute,
            attack_type=attack_type,
            roles=self._normalize_enum_list(merged.get("roles"), HeroRole),
            legs=self._require_int(merged.get("legs")),
            image=self._normalize_str(merged.get("img")) or "",
            icon=self._normalize_str(merged.get("icon")) or "",
            base_health=self._require_int(merged.get("base_health")),
            base_health_regen=self._require_float(merged.get("base_health_regen")),
            base_mana=self._require_int(merged.get("base_mana")),
            base_mana_regen=self._require_float(merged.get("base_mana_regen")),
            base_armor=self._require_float(merged.get("base_armor")),
            base_magic_resistance=self._require_int(merged.get("base_mr")),
            base_attack_min=self._require_int(merged.get("base_attack_min")),
            base_attack_max=self._require_int(merged.get("base_attack_max")),
            base_attack_time=self._require_int(merged.get("base_attack_time")),
            base_strength=self._require_int(merged.get("base_str")),
            base_agility=self._require_int(merged.get("base_agi")),
            base_intelligence=self._require_int(merged.get("base_int")),
            strength_gain=self._require_float(merged.get("str_gain")),
            agility_gain=self._require_float(merged.get("agi_gain")),
            intelligence_gain=self._require_float(merged.get("int_gain")),
            attack_point=self._require_float(merged.get("attack_point")),
            attack_range=self._require_int(merged.get("attack_range")),
            projectile_speed=self._require_int(merged.get("projectile_speed")),
            attack_rate=self._require_float(merged.get("attack_rate")),
            move_speed=self._require_int(merged.get("move_speed")),
            turn_rate=self._normalize_float(merged.get("turn_rate")),
            captains_mode_enabled=self._require_bool(merged.get("cm_enabled")),
            day_vision=self._require_int(merged.get("day_vision")),
            night_vision=self._require_int(merged.get("night_vision")),
            abilities=abilities,
            talents=talents,
            lore=self._normalize_str(merged.get("lore")) or "",
            raw=dict(merged),
        )

    def list_heroes(self, merged_heroes: Sequence[dict[str, Any]]) -> list[Hero]:
        """Build Hero models from merged /heroes + /constants/heroes payloads."""
        return [self.normalize_hero(merged) for merged in merged_heroes]

    def _require_bool(self, value: Any) -> bool:
        normalized = self._normalize_bool(value)
        return normalized if normalized is not None else False

    def _require_int(self, value: Any) -> int:
        normalized = self._normalize_int(value)
        return normalized if normalized is not None else 0

    def _require_float(self, value: Any) -> float:
        normalized = self._normalize_float(value)
        return normalized if normalized is not None else 0.0

    def _normalize_float(
        self, value: Any, default: float | None = None
    ) -> float | None:
        if value is None:
            return default
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return default
        return default

    def _require_bool_or_int(self, value: Any) -> bool | int:
        normalized = self._normalize_bool_or_int(value)
        return normalized if normalized is not None else False

    def _normalize_bool(self, value: Any, default: bool | None = None) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lower = value.strip().lower()
            if lower in {"yes", "true", "1"}:
                return True
            if lower in {"no", "false", "0"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    def _normalize_int(self, value: Any, default: int | None = None) -> int | None:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return default
        return default

    def _normalize_bool_or_int(
        self, value: Any, default: bool | int | None = None
    ) -> bool | int | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip().lower()
            if stripped in {"yes", "true", "1"}:
                return True
            if stripped in {"no", "false", "0"}:
                return False
            try:
                return int(stripped)
            except ValueError:
                return default
        return default

    def _normalize_str(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    def _humanize_slug(self, slug: str) -> str:
        return slug.replace("_", " ").title()

    def _normalize_enum(self, value: Any, enum_type: type[E]) -> E | None:
        if value is None:
            return None
        if isinstance(value, list):
            for item in value:
                try:
                    return enum_type(item)
                except ValueError:
                    continue
            return None
        try:
            return enum_type(value)
        except ValueError:
            return None

    def _normalize_str_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    def _normalize_dict_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [entry for entry in value if isinstance(entry, dict)]

    def _normalize_attributes(self, value: Any) -> list[Attribute]:
        attributes: list[Attribute] = []
        for entry in self._normalize_dict_list(value):
            raw_value = entry.get("value", "")
            attributes.append(
                Attribute(
                    key=str(entry.get("key", "")),
                    value=[str(item) for item in raw_value]
                    if isinstance(raw_value, list)
                    else str(raw_value),
                    display=entry.get("display", entry.get("header")),
                    generated=bool(entry.get("generated", False)),
                )
            )
        return attributes

    def _normalize_abilities(self, value: Any) -> list[ItemAbility]:
        abilities: list[ItemAbility] = []
        for entry in self._normalize_dict_list(value):
            ability_type = self._normalize_enum(entry.get("type"), ItemAbilityType)
            if ability_type is None:
                continue
            abilities.append(
                ItemAbility(
                    type=ability_type,
                    title=str(entry.get("title", "")),
                    description=str(entry.get("description", "")),
                )
            )
        return abilities

    def _normalize_behaviors(self, value: Any) -> bool | list[AbilityBehavior]:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            values = [part.strip() for part in value.split(",") if part.strip()]
        else:
            values = self._normalize_str_list(value)

        behaviors: list[AbilityBehavior] = []
        for item in values:
            try:
                behaviors.append(AbilityBehavior(item))
            except ValueError:
                continue

        return behaviors if behaviors else False

    def _normalize_target_team(self, value: Any) -> ItemTargetTeam | None:
        normalized = self._normalize_str_list(value)
        if not normalized:
            return None
        return self._normalize_enum(normalized[0], ItemTargetTeam)

    def _normalize_target_types(self, value: Any) -> list[ItemTargetType]:
        return self._normalize_enum_list(value, ItemTargetType)

    def _normalize_enum_list(self, value: Any, enum_type: type[E]) -> list[E]:
        return [
            enum_value
            for entry in self._normalize_str_list(value)
            if (enum_value := self._normalize_enum(entry, enum_type)) is not None
        ]

    def _normalize_float_list(self, value: Any) -> list[float]:
        """Normalize a scalar or list of numeric strings, skipping unparseable entries."""
        entries = value if isinstance(value, list) else [value]
        return [
            normalized
            for entry in entries
            if (normalized := self._normalize_float(entry)) is not None
        ]

    def _normalize_components(self, value: Any) -> list[str]:
        return self._normalize_str_list(value)
