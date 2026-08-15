"""Tests for item constants registry behavior."""

import pytest

from opendota_sdk.constants import ConstantsRegistry


class StubTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def request_json(self, *, method, path):
        self.calls += 1
        assert method == "GET"
        assert path == "/constants/items"
        return self.payload


@pytest.mark.asyncio
async def test_get_items_fetches_once_and_reuses_cache():
    transport = StubTransport(
        {
            "blink": {"id": 1, "dname": "Blink Dagger"},
            "branches": {"id": 2, "dname": "Iron Branch"},
        }
    )
    registry = ConstantsRegistry(transport)

    first = await registry.get_items()
    second = await registry.get_items()

    assert transport.calls == 1
    assert first == second
    assert registry.item_data_ready is True
    assert first[0]["name"] in {"blink", "branches"}


@pytest.mark.asyncio
async def test_get_item_supports_lookup_by_id_and_name():
    transport = StubTransport(
        {
            "blink": {"id": 1, "dname": "Blink Dagger"},
        }
    )
    registry = ConstantsRegistry(transport)

    by_id = await registry.get_item(item_id=1)
    by_name = await registry.get_item(item_name="blink")

    assert by_id == by_name
    assert by_id == {"id": 1, "dname": "Blink Dagger", "name": "blink"}


@pytest.mark.asyncio
async def test_get_item_requires_exactly_one_lookup_key():
    registry = ConstantsRegistry(StubTransport({}))

    with pytest.raises(ValueError, match="Either item_id or item_name"):
        await registry.get_item()

    with pytest.raises(ValueError, match="Provide either item_id or item_name"):
        await registry.get_item(item_id=1, item_name="blink")
