from typing import Any

from opendota_sdk.http._transport import AsyncHTTPTransport


class ConstantsRegistry:
    def __init__(self, transport: AsyncHTTPTransport) -> None:
        self._transport = transport
        self._ids_by_name: dict[str, int] = {}
        self._items_by_id: dict[int, dict[str, Any]] = {}

    @property
    def item_data_ready(self) -> bool:
        return bool(self._items_by_id)

    async def _fetch_item_data(self) -> None:
        items_data = await self._transport.request_json(
            method="GET", path="/constants/items"
        )

        for name, data in items_data.items():
            item_id = data["id"]
            data["name"] = name

            self._ids_by_name[name] = item_id
            self._items_by_id[item_id] = data

    async def get_items(self) -> list[dict[str, Any]]:
        if not self.item_data_ready:
            await self._fetch_item_data()
        return list(self._items_by_id.values())

    async def get_item(
        self, *, item_id: int | None = None, item_name: str | None = None
    ) -> dict[str, Any] | None:
        if item_id is None and item_name is None:
            raise ValueError("Either item_id or item_name must be provided.")

        if item_id is not None and item_name is not None:
            raise ValueError("Provide either item_id or item_name, not both.")

        if not self.item_data_ready:
            await self._fetch_item_data()

        if item_id is not None:
            return self._items_by_id.get(item_id)

        if item_name is not None:
            item_id = self._ids_by_name.get(item_name)
            if item_id is not None:
                return self._items_by_id.get(item_id)

        return None
