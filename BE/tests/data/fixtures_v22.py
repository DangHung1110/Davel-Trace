"""A minimal, valid v2.2 POI record for unit tests (DATA_SPEC.md section 2)."""

PROVENANCE_GROUPS = ("name", "location", "category", "status", "hours", "price", "dwell",
                     "tags", "popularity")


def rec(pid="osm:node/1", tier="medium", kind="fixed", open_=("08:00-17:00",),
        status="active", role="attraction", category="museum_indoor", **extra):
    lo, hi = {"free": (0, 0), "included": (0, 0), "cheap": (20_000, 60_000),
              "medium": (100_000, 300_000), "expensive": (600_000, 900_000),
              None: (None, None)}[tier]
    p = {
        "poi_id": pid, "name": "Bảo tàng X", "name_raw": "Bảo tàng X", "name_en": None,
        "lat": 16.06, "lon": 108.22, "category": category, "role": role,
        "status": status, "status_reason": None if status == "active" else "x",
        "zone": "trung_tam", "cluster_id": None, "alt_group": None, "requires_ticket_of": None,
        "hours": {"open": list(open_), "kind": kind, "closed_days": [], "access_window": None,
                  "archetype": "bao_tang"},
        "price": {"tier": tier, "min_vnd": lo, "max_vnd": hi, "note": None},
        "dwell": {"p25": 30, "p50": 60, "p75": 90},
        "tags": {"indoor": True, "effort": 1, "kid_friendly": True,
                 "party": ["solo", "couple", "family", "group"], "good_times": ["morning"],
                 "time_budget": "half_day", "on_request": False, "sun_exposure": 0.05,
                 "outdoor_exposure": 0.1, "rain_cover": "enclosed", "weather_sensitive": False},
        "time_profile": "indoor_flat",
        "popularity": {"signature": False, "audience": None, "prize_prior": 0.5,
                       "wikidata_sitelinks": None, "wikipedia_views_90d": None},
        "description": {"text": None, "source": None, "license": None},
        "ext_ids": {"osm": None, "wikidata": None, "overture": None, "google_place_id": None},
        "provenance": {k: {"source": "x", "verified_by": "inferred", "confidence": 0.5,
                           "evidence_url": None, "verified_at": None, "note": None}
                       for k in PROVENANCE_GROUPS},
        "data_version": "v2.2", "valid_from": "2026-11-19", "valid_to": None,
    }
    p.update(extra)
    return p
