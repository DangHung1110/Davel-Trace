"""Enrich snapshot weather labels via the audit-safe T063 classifier (stdlib only).

Pipeline role
-------------
This is the snapshot wiring step for ``BE.ml.weather_label.labeler.classify_poi``.
For every POI it:

1. Takes the human I/O/B audit (``SPOT_CHECK.md`` via :func:`parse_audit`, or an
   explicit ``audit`` mapping).  Audit labels win for ``space`` and the existing
   ``weather_sensitive`` semantics (I -> False, O/B -> True).
2. Passes per-POI OSM evidence from ``osm_by_poi[poi_id]`` when supplied, else
   the POI's existing ``osm_evidence`` payload.
3. Stores classifier provenance (space/rain source, confidence, evidence,
   conflict) and updates ``smart_tags.space`` / ``smart_tags.rain_protection``.
   The legacy ``rain-proof`` time tag is removed.

It deliberately does **not** modify intensity, duration, price or party tags.

CLI
---
  python BE/ml/data/enrich_snapshot.py --snapshot BE/data/snapshots/danang-v1 --check
  python BE/ml/data/enrich_snapshot.py --snapshot BE/data/snapshots/danang-v1 \
      --osm-json path/to/osm_by_poi.json --apply

``--check`` is read-only.  ``--apply`` writes ``pois.json``,
``RELABEL_REPORT.json``, ``RELABEL_REPORT.md`` and ``weather_review_200.json``
into the snapshot directory.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.ml.weather_label.labeler import classify_poi  # noqa: E402

TOOL_VERSION = "t063-weather-wiring-v1"
REVIEW_LIMIT = 200
REVIEW_FILENAME = "weather_review_200.json"
REPORT_JSON = "RELABEL_REPORT.json"
REPORT_MD = "RELABEL_REPORT.md"

# Canonical -> (intensity, weather_sensitive).  These remain for the other
# data-build helpers that import them; ``enrich()`` itself no longer writes
# intensity (T063 wiring must not touch intensity/duration/price/party).
INTENSITY_DEFAULT = {
    "nature": 3,
    "beach": 2,
    "attraction": 2,
    "park": 2,
    "landmark": 1,
    "museum": 1,
    "market": 1,
    "restaurant": 1,
    "cafe": 1,
    "transport": 1,
    "lodging": 1,
    "spa": 1,
    "bar": 1,
}

WS_DEFAULT = {
    "nature": True,
    "beach": True,
    "attraction": True,
    "park": True,
    "landmark": True,
    "museum": False,
    "market": False,
    "restaurant": False,
    "cafe": False,
    "transport": False,
    "lodging": False,
    "spa": False,
    "bar": False,
}

AUDIT_WS = {"I": False, "O": True, "B": True}

_AUDIT_SPACE = {"I": "indoor", "O": "outdoor", "B": "both"}
_AUDIT_ALIASES = {
    "I": "I", "INDOOR": "I",
    "O": "O", "OUTDOOR": "O",
    "B": "B", "BOTH": "B",
}

_LINE_RE = re.compile(
    r"^-\s*\[[ x]\]\s*(?P<name>.*?)\s*\|\s*(?P<type>.*?)\s*\|.*?"
    r"indoor/outdoor=(?P<io>[IOB?\-])\s*=>", re.UNICODE)


def parse_audit(path: str) -> dict[str, str]:
    """SPOT_CHECK.md -> {poi name: I/O/B/?/-}."""
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _LINE_RE.match(line.strip())
            if m:
                out[m.group("name").strip()] = m.group("io")
    return out


def _as_audit_label(raw) -> str | None:
    if raw is None:
        return None
    return _AUDIT_ALIASES.get(str(raw).strip().upper())


def _audit_label(poi: dict, audit: dict | None) -> str | None:
    """Return the effective human I/O/B label (audit first, then io_label)."""
    audit = audit or {}
    raw = audit.get(poi.get("name", ""))
    label = _as_audit_label(raw)
    if label:
        return label
    pid = poi.get("poi_id")
    for key in (pid, str(pid)):
        label = _as_audit_label(audit.get(key))
        if label:
            return label
    return _as_audit_label(poi.get("io_label"))


def _lookup_osm(poi: dict, osm_by_poi: dict | None):
    """Per-POI OSM list/element, falling back to the POI's existing payload."""
    if osm_by_poi:
        pid = poi.get("poi_id")
        for key in (pid, str(pid)):
            if key in osm_by_poi:
                return osm_by_poi[key]
    return poi.get("osm_evidence")


def _old_rain_protection(smart_tags: dict):
    value = smart_tags.get("rain_protection")
    if value is not None:
        return value
    if "rain-proof" in (smart_tags.get("time") or []):
        return "rain-proof"
    return "unknown"


def _confidence_key(value) -> str:
    try:
        return str(round(float(value), 3))
    except (TypeError, ValueError):
        return str(value)


def _priority(poi: dict, old_space: str, new_space: str) -> int:
    """Deterministic review ranking: changed outdoor first, rest last."""
    changed = old_space != new_space
    if changed and new_space == "outdoor":
        return 0
    if changed:
        return 1
    if poi.get("space_conflict"):
        return 2
    try:
        confidence = float(poi.get("space_confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < 0.5:
        return 3
    if poi.get("space_source") == "canonical":
        return 4
    return 5


def build_weather_review_rows(pois: list[dict], old_by_id: dict | None = None,
                              limit: int = REVIEW_LIMIT) -> list[dict]:
    """Build the stable designer-review rows (exactly ``limit`` when possible).

    Rows are ordered by: changed->outdoor, any changed label, conflicts, low
    confidence, canonical strata, then remaining lowest-confidence POIs.
    Ties break on ``poi_id`` so repeated runs are deterministic.
    """
    old_by_id = old_by_id or {}
    ranked: list[tuple[int, float, str, dict]] = []

    for p in pois:
        st = p.get("smart_tags") or {}
        pid = p.get("poi_id")
        old = old_by_id.get(pid) or old_by_id.get(str(pid)) or {}
        old_space = old.get("space", st.get("space", "unknown"))
        old_rain = old.get("rain_protection", _old_rain_protection(st))
        new_space = st.get("space", p.get("space", "unknown"))
        new_rain = st.get("rain_protection",
                          p.get("rain_protection", "unknown"))
        try:
            confidence = float(p.get("space_confidence"))
        except (TypeError, ValueError):
            confidence = 0.0
        row = {
            "poi_id": pid,
            "name": p.get("name", ""),
            "type": p.get("type", ""),
            "lat": p.get("lat"),
            "lon": p.get("lon"),
            "old_space": old_space,
            "suggested_space": new_space,
            "space_source": p.get("space_source", "unknown"),
            "space_confidence": p.get("space_confidence"),
            "space_evidence": list(p.get("space_evidence") or []),
            "old_rain_protection": old_rain,
            "rain_protection": new_rain,
            "rain_protection_confidence": p.get(
                "rain_protection_confidence"),
            "rain_protection_evidence": list(
                p.get("rain_protection_evidence") or []),
            "space_conflict": bool(p.get("space_conflict")),
        }
        ranked.append((_priority(p, old_space, new_space),
                       confidence, str(pid), row))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    return [row for _, _, _, row in ranked[:limit]]


def enrich(pois: list[dict], audit: dict[str, str],
           osm_by_poi: dict | None = None) -> dict:
    """Apply the T063 classifier to every POI in place.

    Only weather fields and ``smart_tags.space``/``rain_protection``/``time``
    are changed.  Returns a deterministic report used by the CLI and tests.
    """
    transitions: Counter = Counter()
    sources: Counter = Counter()
    confidences: Counter = Counter()
    rain_dist: Counter = Counter()
    rain_transitions: Counter = Counter()
    conflict_ids: list = []
    changed: list[dict] = []
    rain_changed: list[dict] = []
    old_by_id: dict = {}
    n_audit = 0
    n_preserved_audit = 0

    for p in pois:
        if not isinstance(p, dict):
            continue
        st = p.get("smart_tags")
        if not isinstance(st, dict):
            st = {}
            p["smart_tags"] = st

        pid = p.get("poi_id")
        old_space = st.get("space", "unknown")
        old_rain = _old_rain_protection(st)
        old_by_id[pid] = {"space": old_space, "rain_protection": old_rain}

        audit_label = _audit_label(p, audit)
        if audit_label:
            p["io_label"] = audit_label
            n_audit += 1
        else:
            p["io_label"] = None

        result = classify_poi(
            p, audit=audit_label, osm=_lookup_osm(p, osm_by_poi))

        new_space = result["space"]
        new_rain = result["rain_protection"]

        p["weather_sensitive"] = result["weather_sensitive"]
        p["ws_source"] = ("audit" if audit_label
                          else f"classifier_{result['space_source']}")
        p["space_source"] = result["space_source"]
        p["space_confidence"] = result["space_confidence"]
        p["space_evidence"] = list(result["space_evidence"])
        p["space_conflict"] = list(result["space_conflict"])
        p["rain_protection"] = new_rain
        p["rain_protection_source"] = result["rain_protection_source"]
        p["rain_protection_confidence"] = result["rain_protection_confidence"]
        p["rain_protection_evidence"] = list(
            result["rain_protection_evidence"])

        st["space"] = new_space
        st["rain_protection"] = new_rain
        time_tags = st.get("time")
        if isinstance(time_tags, (list, tuple)):
            st["time"] = [t for t in time_tags if t != "rain-proof"]

        transitions[f"{old_space}->{new_space}"] += 1
        rain_transitions[f"{old_rain}->{new_rain}"] += 1
        sources[result["space_source"]] += 1
        confidences[_confidence_key(result["space_confidence"])] += 1
        rain_dist[new_rain] += 1

        if result["space_conflict"]:
            conflict_ids.append(pid)

        if old_space != new_space:
            changed.append({
                "poi_id": pid,
                "name": p.get("name", ""),
                "old_space": old_space,
                "new_space": new_space,
                "space_source": result["space_source"],
                "space_confidence": result["space_confidence"],
                "space_evidence": list(result["space_evidence"]),
            })
        if old_rain != new_rain:
            rain_changed.append({
                "poi_id": pid,
                "name": p.get("name", ""),
                "old_rain_protection": old_rain,
                "new_rain_protection": new_rain,
                "rain_protection_source": result["rain_protection_source"],
                "rain_protection_confidence": result[
                    "rain_protection_confidence"],
                "rain_protection_evidence": list(
                    result["rain_protection_evidence"]),
            })

        if audit_label:
            expected_space = _AUDIT_SPACE[audit_label]
            expected_ws = AUDIT_WS[audit_label]
            if (new_space == expected_space
                    and result["weather_sensitive"] == expected_ws):
                n_preserved_audit += 1

    changed.sort(key=lambda item: str(item["poi_id"]))
    rain_changed.sort(key=lambda item: str(item["poi_id"]))
    conflict_ids.sort(key=str)
    review_rows = build_weather_review_rows(pois, old_by_id=old_by_id)
    changed_space_ids = {item["poi_id"] for item in changed}
    changed_rain_ids = {item["poi_id"] for item in rain_changed}

    return {
        "tool_version": TOOL_VERSION,
        "total": len(pois),
        "audit_labels": n_audit,
        "preserved_audit": n_preserved_audit,
        "space_transitions": dict(sorted(transitions.items())),
        "rain_transitions": dict(sorted(rain_transitions.items())),
        "space_sources": dict(sorted(sources.items())),
        "space_confidence": dict(sorted(confidences.items())),
        "rain_distribution": dict(sorted(rain_dist.items())),
        "conflict_ids": conflict_ids,
        "changed": changed,
        "changed_ids": [item["poi_id"] for item in changed],
        "space_changed_count": len(changed_space_ids),
        "rain_changed": rain_changed,
        "rain_changed_ids": [item["poi_id"] for item in rain_changed],
        "rain_changed_count": len(changed_rain_ids),
        "changed_poi_count": len(changed_space_ids | changed_rain_ids),
        "review_row_count": len(review_rows),
        "review_rows": review_rows,
    }


def _md_count_table(title: str, mapping: dict) -> list[str]:
    lines = [f"### {title}", "", "| key | count |", "|---|---|"]
    for key, value in sorted(mapping.items()):
        lines.append(f"| {key} | {value} |")
    lines.append("")
    return lines


def _markdown_report(report: dict, generated_at: str) -> str:
    lines = [
        "# T063 weather relabel report",
        "",
        f"- Tool version: `{report.get('tool_version', TOOL_VERSION)}`",
        f"- Generated (UTC): {generated_at}",
        f"- POIs: {report.get('total', 0)}",
        f"- Audit labels applied: {report.get('audit_labels', 0)}",
        f"- Audit labels preserved exactly: {report.get('preserved_audit', 0)}",
        f"- Changed space labels: {report.get('space_changed_count', len(report.get('changed', [])))}",
        f"- Changed rain-protection labels: {report.get('rain_changed_count', len(report.get('rain_changed', [])))}",
        f"- Unique POIs with a changed weather label: {report.get('changed_poi_count', len(report.get('changed', [])))}",
        f"- Review rows: {report.get('review_row_count', 0)}",
        "",
        "## Space transitions (old -> new)",
        "",
    ]
    transitions = report.get("space_transitions", {})
    if transitions:
        for key, value in transitions.items():
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(_md_count_table("Space sources",
                                 report.get("space_sources", {})))
    lines.extend(_md_count_table("Space confidence",
                                 report.get("space_confidence", {})))
    lines.extend(_md_count_table("Rain protection",
                                 report.get("rain_distribution", {})))
    lines.extend(_md_count_table("Rain transitions (old -> new)",
                                 report.get("rain_transitions", {})))

    lines.append("## Changed POIs")
    lines.append("")
    changed = report.get("changed", [])
    if not changed:
        lines.append("- none")
    for item in changed:
        evidence = "; ".join(str(e) for e in item.get("space_evidence", []))
        lines.append(
            f"- `{item['poi_id']}` {item.get('name', '')}: "
            f"{item['old_space']} -> {item['new_space']} "
            f"({item.get('space_source', 'unknown')}, "
            f"conf {item.get('space_confidence')})"
            + (f" — {evidence}" if evidence else ""))
    lines.append("")

    lines.append("## Conflict IDs")
    lines.append("")
    conflicts = report.get("conflict_ids", [])
    lines.append(", ".join(str(c) for c in conflicts) if conflicts else "none")
    lines.append("")
    return "\n".join(lines)


def parse_osm_json(path: str) -> dict:
    """Load ``{"by_poi": {poi_id: [elements...]}}`` (flat dict tolerated)."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    by_poi = raw.get("by_poi", raw) if isinstance(raw, dict) else {}
    if not isinstance(by_poi, dict):
        raise ValueError("--osm-json must contain a 'by_poi' object")
    return by_poi


def write_reports(snapshot: str, report: dict,
                  generated_at: str) -> dict:
    """Write RELABEL_REPORT.json/.md and weather_review_200.json."""
    json_path = os.path.join(snapshot, REPORT_JSON)
    md_path = os.path.join(snapshot, REPORT_MD)
    review_path = os.path.join(snapshot, REVIEW_FILENAME)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_markdown_report(report, generated_at))
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(report.get("review_rows", []), f,
                  ensure_ascii=False, indent=2)
    return {"report_json": json_path, "report_md": md_path,
            "review_json": review_path}


def apply_snapshot(snapshot: str, audit: dict[str, str],
                   osm_by_poi: dict | None = None,
                   now: datetime | None = None) -> dict:
    """Enrich + write pois.json and the three weather reports."""
    pois_path = os.path.join(snapshot, "pois.json")
    with open(pois_path, encoding="utf-8") as f:
        data = json.load(f)

    generated_at = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    report = enrich(data["pois"], audit, osm_by_poi)
    report["generated_at"] = generated_at
    data["enriched_at"] = generated_at

    with open(pois_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    report["outputs"] = write_reports(snapshot, report, generated_at)
    return report


def _print_check(report: dict) -> None:
    print(f"tool={report['tool_version']} total={report['total']} "
          f"audit_labels={report['audit_labels']} "
          f"preserved_audit={report['preserved_audit']}")
    print("space transitions:")
    for key, value in report["space_transitions"].items():
        print(f"  {key}: {value}")
    print("space sources:", json.dumps(report["space_sources"],
                                       ensure_ascii=False, sort_keys=True))
    print("space confidence:", json.dumps(report["space_confidence"],
                                          ensure_ascii=False, sort_keys=True))
    print("rain distribution:", json.dumps(report["rain_distribution"],
                                           ensure_ascii=False, sort_keys=True))
    print("rain transitions:", json.dumps(report["rain_transitions"],
                                           ensure_ascii=False, sort_keys=True))
    conflicts = report["conflict_ids"]
    print(f"conflict_ids ({len(conflicts)}): "
          f"{', '.join(str(c) for c in conflicts[:30])}"
          + (" ..." if len(conflicts) > 30 else ""))
    print(f"space_changed={report['space_changed_count']} "
          f"rain_changed={report['rain_changed_count']} "
          f"changed_pois={report['changed_poi_count']} "
          f"review_rows={report['review_row_count']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--osm-json")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    snapshot = args.snapshot
    pois_path = os.path.join(snapshot, "pois.json")
    with open(pois_path, encoding="utf-8") as f:
        data = json.load(f)
    audit = parse_audit(os.path.join(snapshot, "SPOT_CHECK.md"))
    osm_by_poi = parse_osm_json(args.osm_json) if args.osm_json else None
    print(f"pois={len(data['pois'])} audit_labels={len(audit)}")

    if args.check:
        # Dry run: never mutate the loaded snapshot or write reports.
        report = enrich(copy.deepcopy(data["pois"]), audit, osm_by_poi)
        _print_check(report)
        return 0

    if args.apply:
        report = apply_snapshot(snapshot, audit, osm_by_poi)
        print(f"wrote {pois_path}: "
              f"changed={len(report['changed'])} "
              f"review_rows={report['review_row_count']}")
        print("outputs:", json.dumps(report["outputs"], ensure_ascii=False))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
