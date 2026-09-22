# Data Model: Personalized Travel Agent MVP

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
Store: versioned JSON snapshot (`data/snapshots/danang-v1/`) + SQLite runtime.
All entities Pydantic-validated (see `contracts/api.md`).

## Entities

### User
- Fields: `user_id`, `lang` (default `vi`), `party_type`, `trip_purpose` (leisure|business → toggles novelty), `spending_level` 1–3, `pace` 1–3, `fitness` 1–3, `food_prefs[]`, `must_avoid[]`, `long_prefs{}`, `visited[]` ({poi_id, at, rating}).
- Validation: onboarding 5 answers required before first recommendation (FR-050).
- Relations: 1 User → N TripRequests, N Expenses, N EvaluationRecords.

### TripRequest
- Fields: `trip_id`, `user_id`, `origin{lat,lon,label}`, `city` (=`da-nang` MVP), `date`, `start_time`, `end_time`, `days` 1–2, `travelers`, `budget`, `transport[]`, `must_visit[]`, `avoid[]`, `activities[]`, `food_prefs`, `order_prefs[]`.
- Validation: city/time present or clarification (FR-005); budget ≥0; days ≤2.
- State: `draft → confirmed → planned → active → done`; `active` + delta → `replanning`.

### POI (snapshot, TravelEval schema)
- Fields: `poi_id`, `name`, `name_en?`, `type`, `lat`, `lon`, `opening_hours[]`, `visit_min`, `price_level` 1–3, `fee`, `rating`, `tags[]`, `intensity` 1–3, `ambience`, `weather_sensitive` bool, `pros[]`, `cons[]`, `source`, `fetched_at`, `verified` bool.
- Validation: unverified POIs excluded from main plan (FR-013); `fetched_at` required.
- Relations: POI → N Activities; POI pair → transition features.

### Restaurant (extends POI)
- Extra: `cuisine`, `price_range`, `crowd`, `dietary[]`, `reservation` bool, `meal_slots[]`.

### RouteSegment
- Fields: `from_id`, `to_id`, `mode`, `km`, `minutes`, `source` (osrm|cache), `confidence`, `at`.
- Validation: `minutes` MUST come from matrix cache, never haversine-only for feasibility.

### Activity
- Fields: `poi_id`, `kind`, `start`, `end`, `intensity`, `visit_min`, `buffer_min`, `status` (planned|done|cancelled|replaced).
- Transitions: planned → done (time passed) | cancelled (user/disruption) | replaced (replan).

### Itinerary
- Fields: `itinerary_id`, `trip_id`, `version`, `activities[]` ordered, `segments[]`, `total_cost`, `total_km`, `total_min`, `constraint_status{}`, `preference_score`, `explanation[]` ({claim, evidence|inference, source}), `created_at`.
- Validation: gate (FAR=0, VROH=0, B3=0, BCS=1) before quality scores; version++ on every replan (FR-047).

### DynamicEvent
- Fields: `type` (rain|delay|drop_poi|add_req|tired|closure|...), `at`, `source`, `affected[]`, `delta{}`, `severity`, `resolution` (plan|clarify|no_solution).

### Expense
- Fields: `trip_id`, `label`, `amount`, `at`, `kind` (food|ticket|transport|other); trip budget alert thresholds 80%/100%.

### WeatherSnapshot
- Fields: `fetched_at`, `hourly[{at, temp_c, rain_prob}]`, `source` (open-meteo|cache).

### EvaluationRecord
- Fields: `input`, `itinerary_id`, `baseline`, `gate{}`, `soft{}`, `recovery{}`, `pairwise_label?`.
