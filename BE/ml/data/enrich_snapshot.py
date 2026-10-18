"""Enrich full snapshot intensity + weather_sensitive (lane A, stdlib only).

Sources (priority order):
1. SPOT_CHECK.md audit I/O labels (same dir, 49 lines, human):
   I -> weather_sensitive=False, O/B -> True, ?/-/missing -> canonical default.
2. Canonical-category defaults (estimate_duration.canonical_category):
   intensity + weather_sensitive per canonical key.

Provenance (constitution IV): adds io_label / intensity_source /
ws_source per POI; never touches seed snapshot, durations, ratings,
hours, prices. Additive fields only — snapshot.py validation unaffected.

Usage (repo root):
  python BE/ml/data/enrich_snapshot.py --snapshot BE/data/snapshots/danang-v1 --check
  python BE/ml/data/enrich_snapshot.py --snapshot BE/data/snapshots/danang-v1 --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402

# Canonical -> (intensity, weather_sensitive). Rationale: spec US3 orders
# high-intensity (hiking/nature) before low; outdoor canonicals are
# rain-affected. Audit spot-check agrees: beaches/parks O, cafe/restaurant
# I, markets mostly roofed (I), landmarks mixed (B/O -> True).
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
    "attraction": True,   # Ba Na-scale complexes have large outdoor parts
    "park": True,
    "landmark": True,     # bridges/pagodas/communal houses: B/O in audit
    "museum": False,
    "market": False,      # roofed markets per audit; Helio-type O overridden by audit
    "restaurant": False,
    "cafe": False,
    "transport": False,
    "lodging": False,
    "spa": False,
    "bar": False,
}

AUDIT_WS = {"I": False, "O": True, "B": True}

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


def enrich(pois: list[dict], audit: dict[str, str]) -> dict:
    n_audit = n_canon_ws = n_default_int = 0
    conflicts: list[str] = []
    for p in pois:
        canon = canonical_category(p.get("type", ""))
        # intensity: canonical default; unknown canonical keeps existing value
        if canon in INTENSITY_DEFAULT:
            p["intensity"] = INTENSITY_DEFAULT[canon]
            p["intensity_source"] = "canonical_rule"
        else:
            p.setdefault("intensity_source", "crawl_default")
            n_default_int += 1
        # weather: audit I/O wins, else canonical default
        io = audit.get(p.get("name", ""), "?")
        p["io_label"] = io if io in ("I", "O", "B") else None
        if io in AUDIT_WS:
            p["weather_sensitive"] = AUDIT_WS[io]
            p["ws_source"] = "audit"
            n_audit += 1
            if canon in WS_DEFAULT and WS_DEFAULT[canon] != AUDIT_WS[io]:
                conflicts.append(f"{p['name']}: audit {io} vs canonical {canon}")
        else:
            p["weather_sensitive"] = WS_DEFAULT.get(canon, False)
            p["ws_source"] = "canonical_rule" if canon in WS_DEFAULT else "default_false"
            n_canon_ws += 1
    return {"audit_ws": n_audit, "canonical_ws": n_canon_ws,
            "intensity_untouched": n_default_int, "conflicts": conflicts}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    pois_path = os.path.join(args.snapshot, "pois.json")
    with open(pois_path, encoding="utf-8") as f:
        data = json.load(f)
    audit = parse_audit(os.path.join(args.snapshot, "SPOT_CHECK.md"))
    print(f"pois={len(data['pois'])} audit_labels={len(audit)}")

    if args.check:
        import copy
        report = enrich(copy.deepcopy(data["pois"]), audit)
        print(json.dumps(report, ensure_ascii=False, indent=1)[:2000])
        return 0

    if args.apply:
        report = enrich(data["pois"], audit)
        data["enriched_at"] = "2026-10-10"
        with open(pois_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"wrote {pois_path}: " + json.dumps(
            {k: v for k, v in report.items() if k != "conflicts"}, ensure_ascii=False))
        for c in report["conflicts"]:
            print("conflict:", c)
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
