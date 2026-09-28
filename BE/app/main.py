"""FastAPI entry (T001 + T020, lane C). Health + routers. Error envelope
+ logging centralize in T009."""

from fastapi import FastAPI

from BE.app.config import get_settings
from BE.app.routers import itinerary as itinerary_router
from BE.app.routers import parse as parse_router
from BE.app.routers import select as select_router

app = FastAPI(title="Travel Agent BE")
app.include_router(parse_router.router)
app.include_router(itinerary_router.router)
app.include_router(select_router.router)


@app.get("/v1/health")
def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "snapshot": settings.snapshot_name}
