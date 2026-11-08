"""In-process ASGI requests that do not bind a local TCP listener."""

from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient


def request(app, method: str, url: str, **kwargs):
    async def send():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test.local"
        ) as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(send())
