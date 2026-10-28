"""FastAPI entry (T001 + T020, lane C). Health + routers. Error envelope
+ logging centralize in T009."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.routers import expenses as expenses_router
from BE.app.routers import evaluate as evaluate_router
from BE.app.routers import itinerary as itinerary_router
from BE.app.routers import parse as parse_router
from BE.app.routers import replan as replan_router
from BE.app.routers import repair as repair_router
from BE.app.routers import review as review_router
from BE.app.routers import scorer as scorer_router
from BE.app.routers import select as select_router
from BE.app.routers import weather as weather_router

app = FastAPI(title="Travel Agent BE")
# NOTE(test-local, DO NOT COMMIT as-is): allow-all CORS so the local
# harness page (served on another port) can call the API. Restrict to
# app origins before any PR.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(parse_router.router)
app.include_router(itinerary_router.router)
app.include_router(select_router.router)
app.include_router(replan_router.router)
app.include_router(expenses_router.router)
app.include_router(weather_router.router)
app.include_router(evaluate_router.router)
app.include_router(scorer_router.router)
# NOTE(test-local): semantic LLM review for the local test harness only.
app.include_router(review_router.router)
# NOTE(test-local): bounded LLM-guided repair loop (same review + safe swaps).
app.include_router(repair_router.router)


def _validation_message(errors: list[dict]) -> str:
    fields = []
    for item in errors:
        location = ".".join(
            str(part) for part in item.get("loc", ()) if part != "body")
        if location and location not in fields:
            fields.append(location)
    if fields:
        return "du lieu khong hop le: " + ", ".join(fields)
    return "du lieu khong hop le"


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
        request: Request, exc: RequestValidationError):
    return error("VALIDATION_ERROR", _validation_message(exc.errors()), 422)


@app.exception_handler(ValidationError)
async def pydantic_validation_error_handler(
        request: Request, exc: ValidationError):
    return error("VALIDATION_ERROR", _validation_message(exc.errors()), 422)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
        request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "yeu cau khong hop le"
    return error("HTTP_ERROR", message, exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return error("INTERNAL_ERROR", "loi noi bo", 500)


@app.get("/v1/health")
def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "snapshot": settings.snapshot_name}
