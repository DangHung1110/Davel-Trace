"""Schema re-exports (T007-foundation, lane C).

Done: trip (User, TripRequest).
Pending lanes (DO NOT import until those files exist):
  - schemas/poi.py   (POI, Restaurant) — lane A
  - schemas/plan.py  (RouteSegment, Activity, Itinerary) — lane B
  - schemas/eval.py  (DynamicEvent, Expense, WeatherSnapshot,
                      EvaluationRecord) — lane A
"""

from BE.app.schemas.trip import TripRequest, User

# ponytail: cross-lane re-export kept for lane A/B; delete once all schemas
# import directly from schemas/trip|poi|plan|eval.
__all__ = ["TripRequest", "User"]
