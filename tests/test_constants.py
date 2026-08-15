"""Tests for item constants registry behavior."""

import pytest

from opendota_sdk._errors import TransportError
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


@pytest.mark.asyncio
async def test_get_items_injected_name_overwrites_existing_name_key():
    transport = StubTransport(
        {"blink": {"id": 1, "dname": "Blink Dagger", "name": "custom_name"}}
    )
    registry = ConstantsRegistry(transport)

    items = await registry.get_items()

    assert items[0]["name"] == "blink"


@pytest.mark.asyncio
async def test_get_items_returns_independent_list_snapshot():
    transport = StubTransport({"blink": {"id": 1, "dname": "Blink Dagger"}})
    registry = ConstantsRegistry(transport)

    first = await registry.get_items()
    first.append({"id": 999, "name": "mutated"})
    second = await registry.get_items()

    assert len(second) == 1
    assert transport.calls == 1


@pytest.mark.asyncio
async def test_get_item_by_id_not_found_returns_none():
    registry = ConstantsRegistry(
        StubTransport({"blink": {"id": 1, "dname": "Blink Dagger"}})
    )
    assert await registry.get_item(item_id=999) is None


@pytest.mark.asyncio
async def test_get_item_by_name_not_found_returns_none():
    registry = ConstantsRegistry(
        StubTransport({"blink": {"id": 1, "dname": "Blink Dagger"}})
    )
    assert await registry.get_item(item_name="nonexistent") is None


class FailingTransport:
    def __init__(self):
        self.calls = 0

    async def request_json(self, *, method, path):
        self.calls += 1
        raise TransportError("boom")


@pytest.mark.asyncio
async def test_get_items_propagates_transport_failure_and_does_not_cache():
    transport = FailingTransport()
    registry = ConstantsRegistry(transport)

    with pytest.raises(TransportError):
        await registry.get_items()

    assert registry.item_data_ready is False

    with pytest.raises(TransportError):
        await registry.get_items()

    assert transport.calls == 2


@pytest.mark.asyncio
async def test_get_items_with_empty_upstream_payload_never_marks_ready():
    transport = StubTransport({})
    registry = ConstantsRegistry(transport)

    first = await registry.get_items()
    second = await registry.get_items()

    assert first == []
    assert second == []
    assert registry.item_data_ready is False
    assert transport.calls == 2


@pytest.mark.asyncio
async def test_get_items_handles_real_items_json_payload(real_items_json):
    registry = ConstantsRegistry(StubTransport(real_items_json))

    items = await registry.get_items()

    assert len(items) == len(real_items_json)
    assert all("name" in item for item in items)
