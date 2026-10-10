"""Smart-tag enrichment v1 (lane A, stdlib only). Taxonomy agreed 2026-10-09.

Groups (stored in poi["smart_tags"], old tags[] untouched):
  ticket: true | false | null  (entry ticket? null = unknown, never guessed)
  price_band: cheap | medium | expensive | null (known prices only; rule:
    price_band set => ticket true. All null until review/quota data lands,
    except curated Ba Na.)
  space: indoor | outdoor | both        (audit I/O wins, else canonical)
  party: family | couple | solo | group (who it's for)
  time:  sunrise | morning | sunset | night | rain-proof (when)
  budget: quick-stop-30 | half-day | full-day [+ must-go] (time fund)

Sources: canonical_category + audit io_label + p50 + CURATED name list
(famous POIs only — everything else rule-derived, confidence low).
Curated entries are explicit and reviewable; no per-POI web claims.

Usage (repo root):
  python BE/ml/data/enrich_tags.py --snapshot BE/data/snapshots/danang-v1 --check
  python BE/ml/data/enrich_tags.py --snapshot BE/data/snapshots/danang-v1 --apply
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import unicodedata

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


SPACE_DEFAULT = {
    "cafe": "indoor", "restaurant": "indoor", "museum": "indoor",
    "lodging": "indoor", "transport": "indoor",
    "beach": "outdoor", "nature": "outdoor", "park": "outdoor",
    "attraction": "both", "market": "both", "landmark": "both",
}

# Public-access canonicals: entry is genuinely free (beaches, pagodas,
# bridges, markets, parks). museum/attraction: ticketed. Food/lodging/
# transport: no ENTRY ticket (food & room prices are separate — price_band
# stays null until real data). Unknown canonical: null, never guessed.
TICKET_DEFAULT = {
    "museum": True,
    "beach": False, "nature": False, "park": False, "landmark": False,
    "market": False, "cafe": False, "restaurant": False,
    "lodging": False, "transport": False, "attraction": False,
}

# SerpApi dumps beaches/temples/viewpoints into "Điểm thu hút..." (= free),
# so attraction defaults False; only names signalling a paid service win.
PAID_NAME_KEYS = (
    "3d", "paradise", "trickeye", "wonderland", "helio", "food tour",
    "du thuyen", "cruise", "cano", "lan bien", "diving", "snorkel",
    "glamping", "safari", "cap treo", "thang may", "ecopark", "suoi hoa",
    "lai thieu", "mikazuki", "ve ", "ticket",
)

PARTY_DEFAULT = {
    "beach": ["family", "couple", "group"],
    "park": ["family", "couple", "group"],
    "market": ["family", "group"],
    "cafe": ["couple", "solo"],
    "restaurant": ["family", "couple", "group"],
    "museum": ["family", "couple", "solo", "group"],
    "landmark": ["family", "couple", "solo", "group"],
    "attraction": ["family", "couple", "solo", "group"],
    "nature": ["couple", "group"],
    "lodging": ["family", "couple"],
    "transport": ["solo", "group"],
}

TIME_DEFAULT = {
    "beach": ["sunrise", "morning", "sunset"],
    "nature": ["sunrise", "morning"],
    "park": ["morning", "sunset"],
    "market": ["morning"],
    "museum": ["morning", "rain-proof"],
    "attraction": ["morning", "rain-proof"],
    "landmark": ["morning", "sunset"],
    "cafe": ["morning", "rain-proof"],
    "restaurant": ["morning", "night", "rain-proof"],
    "lodging": ["night", "rain-proof"],
    "transport": ["morning"],
}

# norm-name substring -> overrides. Famous POIs only, keep tiny & reviewable.
# 3rd element (optional): canonicals the entry applies to — blocks false
# positives like a restaurant named after a market ("Bếp Chợ Hàn").
CURATED = [
    ("ba na", {"ticket": True, "price_band": "expensive",
               "budget": ["full-day"], "must_go": True}, {"attraction"}),
    ("bana", {"ticket": True, "price_band": "expensive",
              "budget": ["full-day"], "must_go": True}, {"attraction"}),
    ("cau rong", {"time": ["sunset", "night"], "must_go": True}, {"landmark"}),
    ("dragon bridge", {"time": ["sunset", "night"]}, {"landmark"}),
    ("my khe", {"must_go": True}, {"beach"}),
    ("hoi an", {"must_go": True}, {"attraction", "landmark"}),
    ("linh ung", {"time": ["morning"], "must_go": True}, {"landmark"}),
    ("ngu hanh son", {"budget": ["half-day"], "must_go": True}, {"attraction"}),
    ("marble mountain", {"must_go": True}, {"attraction", "landmark"}),
    ("cho han", {"time": ["morning"], "must_go": True}, {"market"}),
    ("han market", {"must_go": True}, {"market"}),
    ("du thuyen", {"ticket": True, "time": ["night"]}, None),
    ("cruise", {"ticket": True, "time": ["night"]}, None),
    ("cho dem", {"time": ["night"], "space": "outdoor"}, {"market"}),
    ("night market", {"time": ["night"]}, {"market"}),
    # SerpApi types real museums as attraction when the name says museum
    ("bao tang", {"ticket": True}, None),
    ("museum", {"ticket": True}, None),
    ("son tra", {"budget": ["half-day"]}, {"nature", "landmark", "beach"}),
    ("hai dang", {"time": ["sunset"]}, None),
    ("lighthouse", {"time": ["sunset"]}, None),
]


def budget_of(p50: int) -> str:
    if p50 <= 45:
        return "quick-stop-30"
    if p50 <= 150:
        return "half-day"
    return "full-day"


def tag_poi(p: dict) -> tuple[dict, str]:
    canon = canonical_category(p.get("type", ""))
    io = p.get("io_label")
    space = {"I": "indoor", "O": "outdoor", "B": "both"}.get(
        io or "", SPACE_DEFAULT.get(canon, "both"))
    tags = {
        "ticket": TICKET_DEFAULT.get(canon, None),
        "price_band": None,
        "space": space,
        "party": list(PARTY_DEFAULT.get(canon, ["group"])),
        "time": list(TIME_DEFAULT.get(canon, ["morning"])),
        "budget": [budget_of((p.get("visit_min") or {}).get("p50", 60))],
    }
    if space == "indoor" and "rain-proof" not in tags["time"]:
        tags["time"] = tags["time"] + ["rain-proof"]
    src = "rule_v1"
    nm = _norm(p.get("name", ""))
    if canon == "attraction" and any(k in nm for k in PAID_NAME_KEYS):
        tags["ticket"] = True
        src = "rule_v1+paid-name"
    for key, ov, allowed in CURATED:
        if key in nm and (allowed is None or canon in allowed):
            for k, v in ov.items():
                if k == "must_go":
                    if v and "must-go" not in tags["budget"]:
                        tags["budget"] = tags["budget"] + ["must-go"]
                else:
                    tags[k] = list(v) if isinstance(v, list) else v
            src = "rule_v1+curated"
    # user rule: known price => ticket exists (future fills honor this too)
    if tags["price_band"] is not None:
        tags["ticket"] = True
    return tags, src


def apply_price_web(pois: list[dict], snapshot_dir: str) -> dict:
    """Overlay price_web.json + hours_web.json (web-verified) by name.

    Name match: exact, then diacritic/case-insensitive, then substring.
    Sets ticket/ticket_vnd/ticket_note/price_band + web_evidence; fills
    opening_hours ONLY when empty. Returns {applied, filled_hours}."""
    path = os.path.join(snapshot_dir, "price_web.json")
    if not os.path.exists(path):
        return {"applied": 0, "filled_hours": 0}
    with open(path, encoding="utf-8") as f:
        web = json.load(f)
    hpath = os.path.join(snapshot_dir, "hours_web.json")
    if os.path.exists(hpath):
        with open(hpath, encoding="utf-8") as f:
            web = {**web, **json.load(f)}

    def _norm(s):
        import unicodedata
        s = unicodedata.normalize("NFD", str(s or "").lower())
        return "".join(c for c in s
                       if unicodedata.category(c) != "Mn").replace("đ", "d")

    norm_index = {_norm(p.get("name", "")): p["name"] for p in pois}

    def lookup(name):
        if name in web:
            return web[name]
        n = _norm(name)
        if n in norm_index and norm_index[n] in web:
            return web[norm_index[n]]
        for k in web:  # substring fallback for spelling variants
            if _norm(k) and (_norm(k) in n or n in _norm(k)):
                return web[k]
        return None

    applied = filled = 0
    for p in pois:
        ev = lookup(p.get("name", ""))
        if not ev:
            continue
        st = p.get("smart_tags", {})
        if "price_band" in ev:
            st["price_band"] = ev["price_band"]
        # explicit ticket verdict wins; price=>ticket only when unstated
        if "ticket" in ev:
            st["ticket"] = ev["ticket"]
        elif st.get("price_band") is not None:
            st["ticket"] = True
        p["smart_tags"] = st
        if "ticket_vnd" in ev:
            p["ticket_vnd"] = ev["ticket_vnd"]
        if ev.get("ticket_note"):
            p["ticket_note"] = ev["ticket_note"]
        if ev.get("price_sources"):
            p["price_sources"] = ev["price_sources"]
        if ev.get("hours_web"):
            p.setdefault("web_evidence", {})["hours_web"] = ev["hours_web"]
        if not p.get("opening_hours") and ev.get("hours_fill"):
            p["opening_hours"] = ev["hours_fill"]
            p["hours_source"] = "web"
            filled += 1
        applied += 1
    return {"applied": applied, "filled_hours": filled}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if args.check:
        from collections import Counter
        c = Counter()
        for p in data["pois"]:
            t, _ = tag_poi(p)
            c["ticket:" + str(t["ticket"])] += 1
            c["price:" + str(t["price_band"])] += 1
            c["space:" + t["space"]] += 1
            c["budget:" + t["budget"][0]] += 1
            for x in t["party"]:
                c["party:" + x] += 1
            for x in t["time"]:
                c["time:" + x] += 1
        print(f"pois={len(data['pois'])}")
        for k in sorted(c):
            print(f"  {k:22s} {c[k]}")
        must = [p["name"] for p in data["pois"]
                if "must-go" in tag_poi(p)[0]["budget"]]
        print(f"must-go={len(must)}:", "; ".join(must[:20]))
        return 0
    if args.apply:
        for p in data["pois"]:
            t, src = tag_poi(p)
            p["smart_tags"] = t
            p["smart_tag_source"] = src
        rep = apply_price_web(data["pois"], args.snapshot)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"tagged {len(data['pois'])} pois -> {path} "
              f"(price_web {rep})")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
