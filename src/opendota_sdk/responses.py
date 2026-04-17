from opendota_sdk.models import Hero
from typing import Any


class HeroesResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data

    def as_typed(self) -> list[Hero]:
        return [Hero(**hero) for hero in self._data]

    def as_raw(self) -> list[dict[str, Any]]:
        return self._data
