"""Snapshot loader + validation (T008, lane A).

Loads the versioned TravelEval JSON snapshot (`data/snapshots/<name>/`)
and validates it against `specs/001-travel-agent-mvp/data-model.md`:

- `fetched_at` REQUIRED at snapshot level AND per POI (R4/R8 provenance).
- `verified` flag REQUIRED per POI; unverified POIs are excluded from the
  main plan (FR-013) via :func:`verified_pois`, never silently dropped.
- POI schema check: required fields, coord ranges, visit_min ordering
  (p25 <= p50 <= p75, p50 > 0), dur_source/dur_confidence vocabularies.
- Matrix check: ids list matches POI ids, n*n cells present.

Stdlib only (Pydantic schemas are lane C T007; this loader must not wait
for them — lanes.md STUB rule).
"""

from __future__ import annotations

import json
import os

REQUIRED_POI_FIELDS = (
    "poi_id", "name", "type", "lat", "lon",
    "visit_min", "dur_source", "dur_confidence",
    "fetched_at", "verified", "source",
)

DUR_SOURCES = ("category_rule", "llm", "review_mined", "actual", "pending_llm")
DUR_CONFIDENCES = ("low", "medium", "high")


def validate_poi(poi: dict) -> list[str]:
    """Return list of error strings (empty = valid)."""
    errors: list[str] = []
    for field in REQUIRED_POI_FIELDS:
        if field not in poi:
            errors.append(f"{poi.get('poi_id', '?')}: missing field '{field}'")
    if errors:
        return errors
    pid = poi["poi_id"]
    if not isinstance(poi["lat"], (int, float)) or not -90 <= poi["lat"] <= 90:
        errors.append(f"{pid}: bad lat {poi['lat']!r}")
    if not isinstance(poi["lon"], (int, float)) or not -180 <= poi["lon"] <= 180:
        errors.append(f"{pid}: bad lon {poi['lon']!r}")
    if not poi.get("fetched_at"):
        errors.append(f"{pid}: fetched_at is required")
    if not isinstance(poi.get("verified"), bool):
        errors.append(f"{pid}: verified must be bool")
    vm = poi.get("visit_min")
    if not isinstance(vm, dict) or any(k not in vm for k in ("p25", "p50", "p75")):
        errors.append(f"{pid}: visit_min must hold p25/p50/p75")
    elif not (vm["p25"] <= vm["p50"] <= vm["p75"] and vm["p50"] > 0):
        errors.append(f"{pid}: visit_min ordering broken {vm}")
    if poi.get("dur_source") not in DUR_SOURCES:
        errors.append(f"{pid}: unknown dur_source {poi.get('dur_source')!r}")
    if poi.get("dur_confidence") not in DUR_CONFIDENCES:
        errors.append(f"{pid}: unknown dur_confidence {poi.get('dur_confidence')!r}")
    return errors


def validate_snapshot(data: dict) -> list[str]:
    """Validate whole snapshot dict; return error list (empty = valid)."""
    errors: list[str] = []
    if not data.get("snapshot"):
        errors.append("missing snapshot name")
    if not data.get("fetched_at"):
        errors.append("snapshot fetched_at is required")
    pois = data.get("pois")
    if not isinstance(pois, list) or not pois:
        return errors + ["pois must be a non-empty list"]
    seen: set[str] = set()
    for poi in pois:
        if poi.get("poi_id") in seen:
            errors.append(f"duplicate poi_id {poi.get('poi_id')}")
        seen.add(poi.get("poi_id"))
        errors.extend(validate_poi(poi))
    return errors


def load_snapshot(snapshot_dir: str) -> dict:
    """Load + validate pois.json; raise ValueError listing all violations."""
    with open(os.path.join(snapshot_dir, "pois.json"), encoding="utf-8") as f:
        data = json.load(f)
    errors = validate_snapshot(data)
    if errors:
        raise ValueError("invalid snapshot " + snapshot_dir + ":\n- " + "\n- ".join(errors))
    return data


def verified_pois(data: dict) -> list[dict]:
    """POIs eligible for the main plan (FR-013: unverified excluded)."""
    return [p for p in data["pois"] if p.get("verified") is True]


def load_matrix(snapshot_dir: str, ids: list[str]) -> dict:
    """Load + validate matrix.json cells against POI ids; raise ValueError."""
    with open(os.path.join(snapshot_dir, "matrix.json"), encoding="utf-8") as f:
        matrix = json.load(f)
    errors: list[str] = []
    if matrix.get("ids") != ids:
        errors.append("matrix ids differ from snapshot POI ids")
    cells = matrix.get("cells", {})
    if len(cells) != len(ids) * len(ids):
        errors.append(f"matrix cells {len(cells)} != {len(ids)}x{len(ids)}")
    for a in ids:
        for b in ids:
            cell = cells.get(f"{a}->{b}")
            if not isinstance(cell, dict) or "minutes" not in cell:
                errors.append(f"matrix missing cell {a}->{b}")
            elif a == b and cell["minutes"] != 0:
                errors.append(f"matrix diagonal {a} must be 0")
            elif a != b and cell["minutes"] <= 0:
                errors.append(f"matrix cell {a}->{b} must be > 0")
    if errors:
        raise ValueError("invalid matrix:\n- " + "\n- ".join(errors))
    return matrix
