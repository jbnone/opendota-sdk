"""Ambient client binding used by model relationship methods."""

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from opendota_sdk._errors import OpenDotaError

if TYPE_CHECKING:
    from opendota_sdk.client import OpenDotaAsyncClient

_active_client: ContextVar["OpenDotaAsyncClient | None"] = ContextVar(
    "opendota_active_client", default=None
)
# Tokens live in the context that created them, so the stack is itself context-local:
# concurrent tasks sharing one client each unwind their own bindings.
_token_stack: ContextVar[tuple[Token["OpenDotaAsyncClient | None"], ...]] = ContextVar(
    "opendota_client_tokens", default=()
)


def active_client() -> "OpenDotaAsyncClient":
    """Return the client bound to the current context."""
    client = _active_client.get()
    if client is None:
        raise OpenDotaError(
            "No active OpenDotaAsyncClient. Use `async with OpenDotaAsyncClient() as client:` "
            "or call client.activate() before using model relationship methods."
        )
    return client


def bind_client(client: "OpenDotaAsyncClient") -> None:
    """Make `client` the active client for the current context."""
    _token_stack.set(_token_stack.get() + (_active_client.set(client),))


def unbind_client() -> None:
    """Restore the client that was active before the most recent bind."""
    stack = _token_stack.get()
    if not stack:
        return
    _active_client.reset(stack[-1])
    _token_stack.set(stack[:-1])
