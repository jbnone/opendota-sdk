from typing import Any

from opendota_sdk._errors import OpenDotaError
from opendota_sdk.http._transport import AsyncHTTPTransport


class AsyncResourceBase:
    def __init__(self, transport: AsyncHTTPTransport, constants: Any) -> None:
        self._transport = transport
        self._constants = constants

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            return await self._transport.request_json(
                method="GET", path=path, params=params
            )
        except OpenDotaError:
            raise
        except Exception as exc:
            raise OpenDotaError(str(exc)) from exc
