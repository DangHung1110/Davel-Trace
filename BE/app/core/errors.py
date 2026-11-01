"""Stable, secret-safe API error primitives."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str
    status: int

    def response(self) -> JSONResponse:
        # Keep the established exact body shape. CorrelationMiddleware adds
        # X-Correlation-ID to every response without breaking old clients.
        return JSONResponse(
            {"error": self.code, "message": self.message},
            status_code=self.status,
        )


def safe_error_response(code: str, message: str, status: int) -> JSONResponse:
    return ApiError(code=code, message=message, status=status).response()
