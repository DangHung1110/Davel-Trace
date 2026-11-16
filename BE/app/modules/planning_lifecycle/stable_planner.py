"""Product boundary over the stable planner's output.

The planner (`BE.app.routers.itinerary` and `BE.app.services`) is the one on
`feat/stable-p1-p4` and is not changed for the product. What the durable
lifecycle stores per alternative is derived here, after the planner answered:

- the five gate families, regrouped from the canonical gate report that
  `/v1/itinerary/select` also runs (`select.evaluate_plan`, over the plan's own
  context: its trip, candidate POIs and travel minutes);
- a deterministic rank and score, the data version and the planner provenance.

Empty plans and plans that fail the gate never become product alternatives; the
planner's own response (`/v1/itinerary`) still returns them, as stable does.
"""

from __future__ import annotations

from BE.app.routers import select as select_router
from BE.app.services import pool

# The stable commit whose planner this boundary was written against. The
# planner files are kept identical to that branch; update this when they change.
PLANNER_SOURCE = "35872c2"

GATE_FAMILIES = (
    ("temporal", ("VROH", "ETB", "TCS")),
    ("financial", ("BCS",)),
    ("movement", ("B3",)),
    ("safety_data", ("FAR", "PROFILE_SAFE")),
    ("traveler_constraints", (
        "A1", "CAFE_CAP", "CATEGORY_CAP", "NO_CONSECUTIVE",
        "NO_ADJACENT_FOOD", "REST_FOLLOWS_LUNCH", "HCS",
    )),
)


def family_report(detailed: dict) -> dict:
    """A `gate.report` result plus its checks grouped into the five families."""
    families = {}
    for family, names in GATE_FAMILIES:
        checks = [{"check": name, "passed": detailed["checks"][name],
                   "score": detailed["scores"][name]} for name in names]
        families[family] = {
            "passed": all(item["passed"] for item in checks),
            "score": min(item["score"] for item in checks),
            "checks": checks,
        }
    return {**detailed, "families": families,
            "failed_families": [name for name, value in families.items()
                                if not value["passed"]]}


def with_product_evidence(planned: dict, data_version: str) -> dict:
    """Planner response -> the same response holding only product alternatives.

    Every kept plan carries `gate` (with `families`), `deterministic_rank`,
    `deterministic_score`, `data_version`, `planner_source` and `shadow`.
    """
    store = select_router.get_store()["plans"]
    selectable = []
    for plan in planned.get("plans") or []:
        # The stored copy keeps the private context the gate needs.
        stored = store.get(plan.get("itinerary_id")) or plan
        detailed = select_router.evaluate_plan(stored)
        if not plan.get("activities") or detailed is None or not detailed["passed"]:
            continue
        kept = dict(plan)
        kept["deterministic_rank"] = len(selectable) + 1
        kept["deterministic_score"] = round(pool.plan_quality(stored), 4)
        kept["gate"] = family_report(detailed)
        kept["data_version"] = data_version
        kept["planner_source"] = PLANNER_SOURCE
        kept["shadow"] = {"status": "disabled", "authoritative": False}
        selectable.append(kept)
    return {**planned, "plans": selectable}
