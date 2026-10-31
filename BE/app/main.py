"""FastAPI entry (T001 + T020, lane C). Health + routers. Error envelope
+ logging centralize in T009."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from BE.app.config import Settings, get_settings
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

# Local dev pages (harness, Flutter web) run on any localhost port.
LOCAL_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
PUBLIC_ROUTERS = (parse_router, itinerary_router, select_router, replan_router,
                  expenses_router, weather_router, evaluate_router, scorer_router)
# Local test harness only: semantic LLM review, the bounded LLM-guided repair
# loop, and the append-only "Chốt plan" log for future weight-learning.
LOCAL_ROUTERS = (review_router, repair_router, accept_router)


def configure(app: FastAPI, settings: Settings) -> None:
    """CORS + routers. A production deploy only answers its own origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=None if settings.is_production else LOCAL_ORIGIN_REGEX,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    for module in PUBLIC_ROUTERS:
        app.include_router(module.router)
    if not settings.is_production:
        for module in LOCAL_ROUTERS:
            app.include_router(module.router)


app = FastAPI(title="Travel Agent BE")
configure(app, get_settings())


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
