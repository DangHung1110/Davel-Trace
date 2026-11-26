"""FastAPI entry: CORS, routers, the error envelope, health.

The planner's routers (feat/stable-p1-p4) keep their exposure rules: the public
ones are always on, the local test-harness ones only outside production. The
product platform's capabilities (feat/product-platform) are mounted after them
in every mode.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from BE.app.config import Settings, get_settings
from BE.app.core.health import build_readiness
from BE.app.core.logging import configure_logging
from BE.app.core.request_context import (
    CorrelationMiddleware,
    get_correlation_id,
)
from BE.app.routers import accept as accept_router
from BE.app.routers import error
from BE.app.routers import expenses as expenses_router
from BE.app.routers import evaluate as evaluate_router
from BE.app.routers import itinerary as itinerary_router
from BE.app.routers import parse as parse_router
from BE.app.routers import planning_evidence as planning_evidence_router
from BE.app.routers import replan as replan_router
from BE.app.routers import repair as repair_router
from BE.app.routers import review as review_router
from BE.app.routers import scorer as scorer_router
from BE.app.routers import select as select_router
from BE.app.routers import weather as weather_router
from BE.app.modules.identity import api as identity_api
from BE.app.modules.identity import google_api
from BE.app.modules.profiles import api as profiles_api
from BE.app.modules.trips import api as trips_api
from BE.app.modules.trips.service import TripService
from BE.app.modules.expenses import api as persistent_expenses_api
from BE.app.modules.catalog import api as catalog_api
from BE.app.modules.catalog.infrastructure import load_catalog
from BE.app.modules.routing import api as routing_api
from BE.app.modules.planning_lifecycle import api as planning_lifecycle_api
from BE.app.modules.ai_assistance import api as ai_assistance_api
from BE.app.modules.trip_groups import api as trip_groups_api
from BE.app.modules.trip_groups import planning_api as group_planning_api
from BE.app.modules.routing.infrastructure import load_matrix, matrix_estimate, osrm_route
from BE.app.modules.identity.service import IdentityError

# Local dev pages (harness, Flutter web) run on any localhost port.
LOCAL_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
PUBLIC_ROUTERS = (parse_router, itinerary_router, select_router, replan_router,
                  expenses_router, weather_router, evaluate_router, scorer_router)
# Local test harness only: semantic LLM review, the bounded LLM-guided repair
# loop, and the append-only "Chốt plan" log for future weight-learning.
LOCAL_ROUTERS = (review_router, repair_router, accept_router)
# Product platform: durable evidence, identity, profiles, trips, expenses,
# catalog, routing, the planning lifecycle and optional AI assistance.
PRODUCT_ROUTERS = (planning_evidence_router, identity_api, google_api,
                   profiles_api, trips_api, persistent_expenses_api,
                   catalog_api, routing_api, planning_lifecycle_api,
                   ai_assistance_api, trip_groups_api, group_planning_api)
log = logging.getLogger("davel.api")


def configure(app: FastAPI, settings: Settings) -> None:
    """CORS + routers. A production deploy only answers its own origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=None if settings.is_production else LOCAL_ORIGIN_REGEX,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Correlation-ID",
            "Range",
            "If-Match",
            "If-Range",
        ],
        expose_headers=["Content-Range", "Accept-Ranges", "ETag"],
    )
    app.add_middleware(CorrelationMiddleware)
    for module in PUBLIC_ROUTERS:
        app.include_router(module.router)
    if not settings.is_production:
        for module in LOCAL_ROUTERS:
            app.include_router(module.router)
    app.state.catalog_reader = load_catalog
    app.state.matrix_reader = load_matrix
    app.state.trip_reader = TripService()
    app.state.route_provider = osrm_route
    app.state.matrix_estimator = matrix_estimate
    for module in PRODUCT_ROUTERS:
        app.include_router(module.router)


configure_logging()
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
    # The envelope hides the traceback from the client; the server log keeps it,
    # or a 500 is invisible to whoever runs the box.
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return error("INTERNAL_ERROR", "loi noi bo", 500)


@app.exception_handler(IdentityError)
async def identity_error_handler(request: Request, exc: IdentityError):
    return identity_api.identity_error_response(exc)


@app.get("/v1/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "snapshot": settings.snapshot_name,
        "correlation_id": get_correlation_id(),
    }


@app.get("/v1/ready")
def readiness():
    payload = build_readiness(
        get_settings(),
        correlation_id=get_correlation_id(),
    )
    if payload["status"] != "ready":
        return JSONResponse(payload, status_code=503)
    return payload
