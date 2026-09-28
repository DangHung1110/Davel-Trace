"""FastAPI entry (T001, lane C). Minimal: app + health. Routers (parse,
itinerary, ...) land in T020; error envelope + logging in T009."""

from fastapi import FastAPI

from BE.app.config import get_settings

app = FastAPI(title="Travel Agent BE")


@app.get("/v1/health")
def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "snapshot": settings.snapshot_name}
