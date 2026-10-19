from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_response(
    code: str, message: str, status_code: int, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.code, exc.message, exc.status_code, exc.details)


def _validation_details(errors: list[dict[str, Any]]) -> dict[str, Any]:
    fields: list[str] = []
    for item in errors:
        location = ".".join(str(part) for part in item.get("loc", ()) if part != "body")
        if location and location not in fields:
            fields.append(location)
    return {"fields": fields}


async def request_validation_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(
        "VALIDATION_ERROR",
        "Dữ liệu yêu cầu không hợp lệ",
        422,
        _validation_details(exc.errors()),
    )


async def pydantic_validation_handler(
    _request: Request, exc: ValidationError
) -> JSONResponse:
    return error_response(
        "VALIDATION_ERROR",
        "Dữ liệu không hợp lệ",
        422,
        _validation_details(exc.errors()),
    )


async def http_error_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Yêu cầu không hợp lệ"
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return error_response(code, message, exc.status_code)


async def unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return error_response("INTERNAL_ERROR", "Lỗi nội bộ", 500)
