"""Model assembler that builds domain models from raw constants payloads."""

from collections.abc import Sequence
from enum import Enum
from typing import Any, TypeVar

from opendota_sdk._records import ItemRecord
from opendota_sdk.models import (
    DamageType,
    Dispellable,
    Item,
    ItemAbility,
    ItemAbilityType,
    ItemAttribute,
    ItemBehavior,
    ItemTargetTeam,
    ItemTargetType,
    ItemQuality,
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

        return Item(
            id=self._require_int(record.id),
            name=self._normalize_str(record.name)
            or self._normalize_str(record.dname)
            or "",
            image=self._normalize_str(record.img) or "",
            cost=self._require_int(record.cost),
            created=self._require_bool(record.created),
            mana_cost=self._require_bool_or_int(record.mc),
            health_cost=self._require_bool_or_int(record.hc),
            cooldown=self._require_bool_or_int(record.cd),
            descriptive_name=self._normalize_str(record.dname) or "",
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
            bkb_pierce=self._normalize_bool(record.bkbpierce),
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

    def _require_bool(self, value: Any) -> bool:
        normalized = self._normalize_bool(value)
        return normalized if normalized is not None else False

    def _require_int(self, value: Any) -> int:
        normalized = self._normalize_int(value)
        return normalized if normalized is not None else 0

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

    def _normalize_attributes(self, value: Any) -> list[ItemAttribute]:
        return [
            ItemAttribute(
                key=str(entry.get("key", "")),
                value=str(entry.get("value", "")),
                display=entry.get("display"),
            )
            for entry in self._normalize_dict_list(value)
        ]

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

    def _normalize_behaviors(self, value: Any) -> bool | list[ItemBehavior]:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            values = [part.strip() for part in value.split(",") if part.strip()]
        else:
            values = self._normalize_str_list(value)

        behaviors: list[ItemBehavior] = []
        for item in values:
            try:
                behaviors.append(ItemBehavior(item))
            except ValueError:
                continue

        return behaviors if behaviors else False

    def _normalize_target_team(self, value: Any) -> ItemTargetTeam | None:
        normalized = self._normalize_str_list(value)
        if not normalized:
            return None
        return self._normalize_enum(normalized[0], ItemTargetTeam)

    def _normalize_target_types(self, value: Any) -> list[ItemTargetType]:
        return [
            enum_value
            for entry in self._normalize_str_list(value)
            if (enum_value := self._normalize_enum(entry, ItemTargetType)) is not None
        ]

    def _normalize_components(self, value: Any) -> list[str]:
        return self._normalize_str_list(value)
