"""Route preview orchestration over public trip/catalog contracts."""

from __future__ import annotations

from uuid import UUID

from BE.app.modules.catalog.application import resolve_place
from BE.app.modules.catalog.domain import CatalogUnavailable
from BE.app.modules.routing.domain import RouteResult, Stop, linear_interpolation


def preview(principal, trip_id: str, activity_ids: list[str], catalog: dict,
            matrix: dict, trip_reader, route_provider, estimate_provider) -> dict:
    if not 2 <= len(activity_ids) <= 25 or len(set(activity_ids)) != len(activity_ids):
        raise ValueError("A route requires 2-25 distinct ordered activities.")
    trip = trip_reader.get(principal, UUID(trip_id))
    activity_map = {
        activity["id"]: activity
        for day in trip.get("days", [])
        for activity in day.get("activities", [])
    }
    stops: list[Stop] = []
    unresolved = 0
    for activity_id in activity_ids:
        activity = activity_map.get(activity_id)
        if activity is None:
            raise LookupError("Activity not found in trip.")
        poi_id = activity.get("poi_id")
        place = resolve_place(catalog, poi_id) if poi_id else None
        if place is None:
            unresolved += 1
            continue
        stops.append(Stop(
            activity_id=activity_id, title=activity["title"], poi_id=poi_id,
            latitude=place["lat"], longitude=place["lon"],
        ))
    if len(stops) < 2:
        skipped = " Một số hoạt động không có địa điểm trong danh mục." if unresolved else ""
        return RouteResult(
            quality="unavailable", source="none", is_real_route=False,
            geometry=None, distance_m=0, duration_s=0,
            warning=("Cần ít nhất hai địa điểm trong danh mục để xem tuyến." + skipped),
        ).to_public()
    try:
        result = route_provider(stops)
    except Exception:
        result = None
    if result is not None:
        public = result.to_public()
        if unresolved:
            public["warning"] = "Một số hoạt động chưa có địa điểm trong danh mục nên đã được bỏ qua."
        return public
    try:
        estimate = estimate_provider(stops, matrix)
    except CatalogUnavailable:
        estimate = None
    if estimate is not None:
        public = estimate.to_public()
        if unresolved:
            public["warning"] = "Một số hoạt động chưa có địa điểm trong danh mục nên đã được bỏ qua."
        return public
    result = linear_interpolation(stops).to_public()
    if unresolved:
        result["warning"] += " Một số hoạt động chưa có POI khả dụng đã được bỏ qua."
    return result
