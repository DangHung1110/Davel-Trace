"""GET /v1/weather (contracts/api.md), backed by the cached forecast service."""

from fastapi import APIRouter

from BE.app.services import weather as weather_svc

router = APIRouter(prefix="/v1", tags=["weather"])


@router.get("/weather")
def get_weather(lat: float, lon: float) -> dict:
    return weather_svc.fetch_forecast(lat, lon)
