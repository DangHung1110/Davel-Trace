"""FastAPI entry (T001 + T020, lane C). Health + routers. Error envelope
+ logging centralize in T009."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from BE.app.config import get_settings
from BE.app.routers import accept as accept_router
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

# N6: the local test harness (`index.html` served by `server.py`) calls this
# API from another origin. The allow-list is EXPLICIT (never "*"): the harness
# origins below are always allowed, and `CORS_ORIGINS` (comma-separated) adds
# more (e.g. a second harness port) at startup. It ADDS rather than replaces
# so a typo in the env var can never silently break the local flow.
HARNESS_ORIGINS = ("http://127.0.0.1:5500", "http://localhost:5500")


def cors_origins() -> list[str]:
    """Harness origins + `CORS_ORIGINS` extras (deduped, no trailing slash)."""
    origins = list(HARNESS_ORIGINS)
    for origin in os.environ.get("CORS_ORIGINS", "").split(","):
        origin = origin.strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
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
# NOTE(test-local): append-only "Chốt plan" log for future weight-learning.
app.include_router(accept_router.router)


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
