"""FastAPI entry point for the AI planner and management MVP."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from BE.app.config import get_settings
from BE.app.database import get_engine
from BE.app.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    pydantic_validation_handler,
    request_validation_handler,
)
from BE.app.routers import error
from BE.app.routers import evaluate as evaluate_router
from BE.app.routers import expenses as expenses_router
from BE.app.routers import itineraries as management_itineraries_router
from BE.app.routers import itinerary as agent_itinerary_router
from BE.app.routers import parse as parse_router
from BE.app.routers import pois as pois_router
from BE.app.routers import profiles as management_profiles_router
from BE.app.routers import replan as replan_router
from BE.app.routers import routes as routes_router
from BE.app.routers import scorer as scorer_router
from BE.app.routers import select as select_router
from BE.app.routers import trips as management_trips_router
from BE.app.routers import weather as weather_router

app = FastAPI(title="Davel Trace API", version="1.0.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _management_path(path: str) -> bool:
    return path.startswith(
        ("/v1/profiles", "/v1/trips", "/v1/pois", "/v1/routes", "/v1/activities")
    )


def _validation_message(errors: list[dict]) -> str:
    fields: list[str] = []
    for item in errors:
        location = ".".join(str(part) for part in item.get("loc", ()) if part != "body")
        if location and location not in fields:
            fields.append(location)
    return "du lieu khong hop le" + ((": " + ", ".join(fields)) if fields else "")


@app.exception_handler(AppError)
async def management_error_handler(request: Request, exc: AppError):
    return await app_error_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    if _management_path(request.url.path):
        return await request_validation_handler(request, exc)
    return error("VALIDATION_ERROR", _validation_message(exc.errors()), 422)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    if _management_path(request.url.path):
        return await pydantic_validation_handler(request, exc)
    return error("VALIDATION_ERROR", _validation_message(exc.errors()), 422)


@app.exception_handler(StarletteHTTPException)
async def starlette_http_error_handler(request: Request, exc: StarletteHTTPException):
    if _management_path(request.url.path):
        return await http_error_handler(request, exc)
    message = exc.detail if isinstance(exc.detail, str) else "yeu cau khong hop le"
    return error("HTTP_ERROR", message, exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception):
    return error("INTERNAL_ERROR", "loi noi bo", 500)


for router in (
    parse_router.router,
    agent_itinerary_router.router,
    select_router.router,
    replan_router.router,
    weather_router.router,
    evaluate_router.router,
    scorer_router.router,
    management_profiles_router.router,
    management_trips_router.router,
    management_itineraries_router.router,
    expenses_router.router,
    pois_router.router,
    routes_router.router,
):
    app.include_router(router)


@app.get("/v1/health")
def health() -> dict[str, str]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    current = get_settings()
    return {"status": "ok", "database": "ready", "snapshot": current.snapshot_name}
