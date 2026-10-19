from fastapi import FastAPI
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
    unhandled_error_handler,
)
from BE.app.routers import expenses, itineraries, pois, profiles, routes, trips

app = FastAPI(title="Davel Trace Management API", version="1.0.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_handler)
app.add_exception_handler(ValidationError, pydantic_validation_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(profiles.router)
app.include_router(trips.router)
app.include_router(itineraries.router)
app.include_router(expenses.router)
app.include_router(pois.router)
app.include_router(routes.router)


@app.get("/v1/health")
def health() -> dict[str, str]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    current = get_settings()
    return {
        "status": "ok",
        "database": "ready",
        "snapshot": current.snapshot_name,
    }
