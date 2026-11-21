"""GET /v1/weather (contracts/api.md), backed by the cached forecast service."""

from fastapi import APIRouter

from BE.app.routers import error
from BE.app.services import weather as weather_svc

router = APIRouter(prefix="/v1", tags=["weather"])


@router.get("/weather")
def get_weather(lat: float, lon: float):
    try:
        return weather_svc.fetch_forecast(lat, lon)
    except RuntimeError as exc:  # offline and no cached forecast: not a crash
        return error("WEATHER_UNAVAILABLE", str(exc)[:200], 503)
