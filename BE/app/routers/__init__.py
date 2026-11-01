"""Routers package (T001, lane C). Endpoint routers (parse, itinerary,
replan, expenses, weather, evaluate) land in T020 per contracts/api.md."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from BE.app.core.errors import safe_error_response


def error(code: str, message: str, status: int) -> JSONResponse:
    """Client-error envelope {error, message} per contracts/api.md."""
    return safe_error_response(code, message, status)
