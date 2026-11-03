"""Retrieval explanation -> public response lists (B4/FR-013/FR-024).

Shared by `routers/itinerary.py` (POST /v1/itinerary) and
`routers/repair.py` (POST /v1/repair): both used to reach across the router
package for `itinerary._explain_retrieval`. The shape is one seam, so it lives
in the service layer and each router imports it directly.

`needs_verification` keeps the retrieval reasons + uncertainty labels and the
FR-031 must-visit flag; `excluded` keeps one reason per POI. Names are added
for the UI only (facts from the snapshot, no invention).
"""

from __future__ import annotations


def explain_retrieval(retrieval: dict, by_id: dict) -> tuple[list[dict], list[dict]]:
    """retrieval output -> (`needs_verification`, `excluded`) public lists."""
    def _name(pid) -> str | None:
        return (by_id.get(pid) or {}).get("name")

    needs = []
    for entry in retrieval.get("needs_verification") or []:
        needs.append({
            "poi_id": entry.get("poi_id"),
            "name": _name(entry.get("poi_id")),
            "must_visit": bool(entry.get("must_visit")),
            "reasons": list(entry.get("reasons") or []),
            "uncertainty": list(entry.get("uncertainty") or []),
        })
    excluded = [{"poi_id": item.get("poi_id"),
                 "name": _name(item.get("poi_id")),
                 "reason": item.get("reason")}
                for item in retrieval.get("excluded") or []]
    return needs, excluded
