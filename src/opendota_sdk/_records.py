from dataclasses import dataclass, field
from typing import Any


def _string_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


@dataclass
class ItemRecord:
    """Raw item payload from OpenDota constants, before domain assembly."""

    id: int
    name: str = ""
    dname: str = ""
    img: str = ""
    cost: int | None = None
    created: bool | None = None
    mc: bool | int | None = None
    hc: bool | int | None = None
    cd: bool | int | None = None
    charges: bool | int | None = None
    components: list[str] | None = None
    attrib: list[dict[str, Any]] | None = None
    abilities: list[dict[str, Any]] | None = None
    behavior: bool | list[str] | str | None = None
    hint: list[str] | None = None
    qual: str | None = None
    dmg_type: str | None = None
    dispellable: str | None = None
    target_team: list[str] | str | None = None
    target_type: list[str] | str | None = None
    tier: int | None = None
    bkbpierce: str | None = None
    desc: str | None = None
    notes: str | None = None
    lore: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "ItemRecord":
        return cls(
            id=int(raw.get("id", 0) or 0),
            name=_string_or_empty(raw.get("name", raw.get("dname", ""))),
            dname=_string_or_empty(raw.get("dname", "")),
            img=_string_or_empty(raw.get("img", "")),
            cost=raw.get("cost"),
            created=raw.get("created"),
            mc=raw.get("mc", raw.get("mana_cost")),
            hc=raw.get("hc", raw.get("health_cost")),
            cd=raw.get("cd", raw.get("cooldown")),
            charges=raw.get("charges"),
            components=raw.get("components"),
            attrib=raw.get("attrib"),
            abilities=raw.get("abilities"),
            behavior=raw.get("behavior"),
            hint=raw.get("hint"),
            qual=raw.get("qual"),
            dmg_type=raw.get("dmg_type"),
            dispellable=raw.get("dispellable"),
            target_team=raw.get("target_team"),
            target_type=raw.get("target_type"),
            tier=raw.get("tier"),
            bkbpierce=raw.get("bkb_pierce", raw.get("bkbpierce")),
            desc=raw.get("desc", raw.get("description")),
            notes=raw.get("notes"),
            lore=raw.get("lore"),
            raw=dict(raw),
        )
