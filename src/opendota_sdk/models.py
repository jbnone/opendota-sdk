from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Item:
    id: int
    name: str
    localized_name: str | None = None
    icon: str | None = None
    cost: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "Item":
        return cls(
            id=int(raw.get("id", 0)),
            name=raw.get("name", raw.get("dname", "")),
            localized_name=raw.get("dname", raw.get("name")),
            icon=raw.get("img"),
            cost=raw.get("cost"),
            raw=raw,
        )

    @classmethod
    def from_constants(cls, raw: dict[str, Any]) -> "Item":
        return cls(
            id=int(raw.get("id", 0)),
            name=raw.get("name", raw.get("dname", "")),
            localized_name=raw.get("dname", raw.get("name")),
            icon=raw.get("img"),
            cost=raw.get("cost"),
            raw=raw,
        )

    def as_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass
class Hero:
    id: int
    name: str
    localized_name: str
    primary_attr: str
    attack_type: str
    roles: list[str]
    legs: int
    img: str | None = None
    icon: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    _loader: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_api(
        cls,
        raw: dict[str, Any],
        constants: dict[str, Any] | None = None,
        loader: Any | None = None,
    ) -> "Hero":
        constants = constants or {}
        return cls(
            id=int(raw["id"]),
            name=raw.get("name", ""),
            localized_name=raw.get("localized_name", raw.get("name", "")),
            primary_attr=raw.get("primary_attr", constants.get("primary_attr", "")),
            attack_type=raw.get("attack_type", constants.get("attack_type", "")),
            roles=raw.get("roles", constants.get("roles", [])) or [],
            legs=int(raw.get("legs", constants.get("legs", 0))),
            img=raw.get("img", constants.get("img")),
            icon=raw.get("icon", constants.get("icon")),
            raw={**constants, **raw},
            _loader=loader,
        )

    @classmethod
    def from_constants(cls, raw: dict[str, Any]) -> "Hero":
        return cls(
            id=int(raw.get("id", 0)),
            name=raw.get("name", ""),
            localized_name=raw.get("localized_name", raw.get("name", "")),
            primary_attr=raw.get("primary_attr", ""),
            attack_type=raw.get("attack_type", ""),
            roles=raw.get("roles", []) or [],
            legs=int(raw.get("legs", 0)),
            img=raw.get("img"),
            icon=raw.get("icon"),
            raw=raw,
        )

    def popular_items(self) -> list[Item]:
        if self._loader is None:
            raise RuntimeError("Hero loader not configured for related fetches")
        return self._loader.popular_items(self.id)

    def matchups(self) -> list[dict[str, Any]]:
        if self._loader is None:
            raise RuntimeError("Hero loader not configured for related fetches")
        return self._loader.matchups(self.id)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.raw)
