"""Request-local correlation IDs for responses and diagnostic logs."""

from __future__ import annotations

import re
from contextvars import ContextVar
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


CORRELATION_HEADER = "X-Correlation-ID"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def new_correlation_id(candidate: str | None = None) -> str:
    if candidate and _VALID_ID.fullmatch(candidate):
        return candidate
    return str(uuid4())


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str:
    value = _correlation_id.get()
    if not value:
        value = new_correlation_id()
        set_correlation_id(value)
    return value


class CorrelationMiddleware:
    """Pure ASGI middleware to avoid buffering streaming responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        correlation_id = new_correlation_id(headers.get(CORRELATION_HEADER))
        token = _correlation_id.set(correlation_id)

        async def send_with_correlation(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[CORRELATION_HEADER] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            _correlation_id.reset(token)
