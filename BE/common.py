"""Shared stdlib glue for BE (one spot for copy-pasted helpers).

T061c survivor: time <-> minutes, opening-hours parsing, plan fee/deadline
and JSON/snapshot reads that were duplicated across `eval/`, `ml/` and the
app services. `BE.app.services.common` re-exports these names, so lane B/C
callers keep their imports while a single implementation lives here.
No config, no classes, no third-party imports (DoD).

ponytail: only genuinely repeated glue lives here. Domain schemas stay in
`app/schemas/` and validated snapshot loading stays in
`app/services/snapshot.py` (intentionally stricter, stdlib-only).
"""

from __future__ import annotations

import json
import os
from typing import Any


def to_min(hhmm: str) -> int:
    """'HH:MM' -> minutes since midnight (well-formed input assumed)."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmm(minutes: int) -> str:
    """Minutes since midnight -> 'HH:MM'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# T061c: the survivor helpers below were copy-pasted across app services /
# eval. They live here once; `BE.app.services.common` re-exports them.
hh = hhmm  # lane-B alias (BE.app.services.common.hh)


def _intervals(spec: str):
    """Yield (open, close) minutes for every 'HH:MM-HH:MM' in `spec`.

    One element may pack several comma-separated intervals, e.g.
    "10:30-14:00, 16:30-22:30". Stray/malformed fragments are skipped as
    closed so bad data cannot raise.
    """
    for part in (spec or "").split(","):
        part = part.strip()
        if part.count("-") != 1:
            continue
        o, c = part.split("-")
        yield to_min(o), to_min(c)


def in_range(start: int, end: int, spec: str) -> bool:
    """True iff [start, end] fits any 'HH:MM-HH:MM' window (wraps midnight)."""
    for o, c in _intervals(spec):
        if o <= c:
            if o <= start and end <= c:
                return True
        elif start >= o or end <= c:
            return True
    return False


def parse_windows(hours: list | None) -> list[tuple[int, int]]:
    """Every 'HH:MM-HH:MM' window of `hours` as same-day minutes, sorted.

    A window that wraps midnight ("17:00-02:00") or ends at "23:59" is
    clipped to the end of the day (1440): a day plan never crosses midnight,
    and the old first-span reader turned such a window into an impossible
    constraint (close < open). WP3: the optimizer chooses one of these.
    """
    out = []
    for spec in hours or []:
        for o, c in _intervals(spec):
            if c <= o or c >= 23 * 60 + 59:
                c = 24 * 60
            out.append((o, c))
    return sorted(set(out))


def parse_hours(hours: list | None) -> tuple[int, int] | None:
    """First 'HH:MM-HH:MM' opening span as minutes, or None when unset."""
    if not hours:
        return None
    for spec in hours:
        for o, c in _intervals(spec):
            return o, c
    return None


# B5 (FULL-AUDIT v2, TAG-ONLY money): price band -> typical per-person spend.
# Thresholds mirror `BE/ml/data/price_from_raw.py` `band()` (cheap <100k,
# medium <=500k, expensive >500k); the midpoint is the "what a visitor
# actually pays" figure, matching the ingest rule that bands a menu by its
# midpoint, not its ceiling.
#
# PRODUCT DECISION (2026-10-29): the band IS the price truth. Chasing exact
# VND per ticket was dropped as too costly/error-prone, so `ticket_vnd` is
# DEPRECATED data (field kept, never read at runtime) and the legacy `fee`
# field is likewise unread. A genuinely free POI sets `free_entry: true`
# (there is no `free` band in the enum); band missing + no `free_entry`
# means "giá chưa xác minh" (unknown, NOT free).
BAND_MIDPOINT = {"cheap": 100_000, "medium": 300_000, "expensive": 700_000}


def effective_fee(poi: dict | None) -> int | None:
    """Known spend for one POI in VND, or None when the price is unknown.

    Order (tag-only v2):
    1. `free_entry is True` — explicit "miễn phí" -> 0;
    2. `smart_tags.price_band` — cheap/medium/expensive -> BAND_MIDPOINT;
    3. otherwise None = "giá chưa xác minh" (FR-024/FR-026 uncertainty).

    `ticket_vnd` and the legacy `fee` field are NOT read: exact ticket chasing
    was dropped (see the BAND_MIDPOINT note). A missing band is UNKNOWN, never
    "miễn phí" — the old `fee = 0` default made all 742 snapshot POIs look
    free, so the budget filter, the BCS gate and `total_cost` were vacuous
    (FULL-AUDIT B5).
    """
    if not poi:
        return None
    price = poi.get("price")
    if isinstance(price, dict) and "tier" in price:
        # v2.1 (WP2): one field, 4 tiers (+ included = paid via parent ticket).
        return TIER_MIDPOINT.get(price.get("tier"))
    if poi.get("free_entry") is True:
        return 0
    band = (poi.get("smart_tags") or {}).get("price_band")
    if isinstance(band, str):
        band = band.strip().lower()
    return BAND_MIDPOINT.get(band)


def total_fee(acts: list[dict], pois: dict) -> int:
    """Sum of KNOWN effective fees (unknown price adds 0, never assumed free)."""
    total = 0
    for a in acts:
        fee = effective_fee(pois.get(a.get("poi_id")))
        if fee is not None:
            total += fee
    return total


def plan_cost(itinerary: dict, pois: dict) -> int:
    """Itinerary cost: explicit `total_cost` wins, else the POI fee sum."""
    if "total_cost" in itinerary:
        return int(itinerary["total_cost"])
    return total_fee(itinerary.get("activities", []), pois)


def deadline(trip: dict, default: str = "18:00") -> int:
    """ETB hard within-day deadline: min(end_time, return_time) minutes."""
    end = to_min(trip.get("end_time", default))
    rt = trip.get("return_time")
    return min(end, to_min(rt)) if rt else end


def status_map(checks: dict) -> dict:
    """Gate booleans -> 1/0 constraint_status map."""
    return {k: (1 if v else 0) for k, v in checks.items()}


def fee_upper(poi: dict | None) -> int | None:
    """Warning ceiling for one POI (v2.1 `price.tier` upper bound)."""
    price = (poi or {}).get("price")
    if isinstance(price, dict) and "tier" in price:
        return TIER_UPPER.get(price.get("tier"))
    return effective_fee(poi)


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_pois(snapshot_dir: str, by_id: bool = False):
    """Read <snapshot_dir>/pois.json -> list of POI views, or {poi_id: view}.

    v2.1 records go through `poi_view` (legacy fields the app reads are
    derived at runtime); v1 / v2.0 records pass through unchanged.
    """
    pois = view_pois(load_json(os.path.join(snapshot_dir, "pois.json"))["pois"], snapshot_dir)
    return {p["poi_id"]: p for p in pois} if by_id else pois


# --------------------------------------------------------------------------
# danang-v2.1 adapter (DATA_SPEC_v2_1.md section 1.5, DATA_FIX_PLAN WP1)
# --------------------------------------------------------------------------

DATA_VERSION_V21 = "v2.1"
GOOGLE_POLICIES = ("demo_phi_thuong_mai", "cach_ly")
# Q3: demo until prize_prior existed (WP6); gold v2.1 passes under cach_ly
# (BE/eval/gold/gold_v2.json), so the clean policy is the default now.
# GOOGLE_POLICY=demo_phi_thuong_mai re-enables quarantined Google values.
DEFAULT_GOOGLE_POLICY = "cach_ly"

# One price field: per-person spend for one visit (DATA_SPEC_v2_1 price table).
# midpoint = planned spend, upper = warning ceiling. `included` costs 0 here;
# the parent ticket (`requires_ticket_of`) is paid once.
PRICE_TIERS = ("free", "cheap", "medium", "expensive", "included")
TIER_MIDPOINT = {"free": 0, "included": 0, "cheap": 50_000, "medium": 250_000,
                 "expensive": 850_000}
TIER_UPPER = {"free": 0, "included": 0, "cheap": 100_000, "medium": 500_000,
              "expensive": 1_200_000}
TIER_RANK = {"free": 1, "included": 1, "cheap": 1, "medium": 2, "expensive": 3}


def tier_of_vnd(vnd: float | None) -> str | None:
    """VND per person -> price tier (free / <100k / 100-500k / >500k)."""
    if vnd is None:
        return None
    if vnd <= 0:
        return "free"
    if vnd < 100_000:
        return "cheap"
    if vnd <= 500_000:
        return "medium"
    return "expensive"


# v2.1 category -> legacy English `cat` the v1 services compare against.
LEGACY_CAT = {
    "beach": "beach", "viewpoint": "viewpoint", "outdoor_landmark": "landmark",
    "religious": "landmark", "museum_indoor": "museum", "day_market": "market",
    "night_market": "market", "restaurant": "restaurant", "cafe": "cafe",
    "nightlife": "bar", "wellness": "spa", "paid_attraction": "attraction",
    "lodging": "lodging",
}
def legacy_cat(category: str | None, archetype: str | None = None) -> str | None:
    """v2.1 category -> legacy `cat`, split like v1 so the HARD daily
    category cap (one landmark / attraction / nature / museum per day) keeps
    its v1 meaning: religious stays `landmark` (v1 pagodas), an outdoor
    landmark is `nature` (natural-site hours archetype), `museum` (gated
    site) or `attraction`."""
    if category == "outdoor_landmark":
        return {"ngoai_troi_tu_nhien": "nature", "bao_tang": "museum"}.get(archetype, "attraction")
    return LEGACY_CAT.get(category, category)


# Clean (non-Google) display label for the legacy free-text `type`.
LEGACY_TYPE_VI = {
    "beach": "Bãi biển", "viewpoint": "Điểm ngắm cảnh",
    "outdoor_landmark": "Điểm tham quan", "religious": "Chùa / cơ sở thờ tự",
    "museum_indoor": "Bảo tàng", "day_market": "Chợ", "night_market": "Chợ đêm",
    "restaurant": "Nhà hàng", "cafe": "Quán cà phê", "nightlife": "Quán bar",
    "wellness": "Spa", "paid_attraction": "Khu vui chơi có vé", "lodging": "Khách sạn",
}
# v2.1 tags key -> legacy smart_tags key (renamed in v2.1)
_TAG_RENAME_BACK = {"good_times": "time", "time_budget": "budget"}
_TAG_NOT_SMART = {"indoor", "effort", "kid_friendly", "weather_sensitive"}

_QUARANTINE_CACHE: dict[str, dict] = {}


def google_policy() -> str:
    """Runtime Google policy (`GOOGLE_POLICY` env), never decided at build."""
    pol = os.environ.get("GOOGLE_POLICY", DEFAULT_GOOGLE_POLICY)
    return pol if pol in GOOGLE_POLICIES else DEFAULT_GOOGLE_POLICY


def load_quarantine(snapshot_dir: str | None) -> dict:
    """{poi_id: google values} from <snapshot_dir>/quarantine_google.json."""
    if not snapshot_dir:
        return {}
    path = os.path.join(snapshot_dir, "quarantine_google.json")
    key = os.path.abspath(path)
    if key not in _QUARANTINE_CACHE:
        try:
            _QUARANTINE_CACHE[key] = load_json(path).get("items", {})
        except (FileNotFoundError, NotADirectoryError, ValueError):
            _QUARANTINE_CACHE[key] = {}
    return _QUARANTINE_CACHE[key]


def is_v21(poi: dict | None) -> bool:
    return bool(poi) and poi.get("data_version") == DATA_VERSION_V21


def poi_view(poi: dict, policy: str | None = None, quarantine: dict | None = None) -> dict:
    """v2.1 record -> dict with BOTH the v2.1 fields and the legacy fields the
    current services read (`opening_hours`, `visit_min`, `smart_tags`,
    `free_entry`, `rating`, `price_level`, `verified`, `type`, `cat`, `tags`,
    `intensity`, `weather_sensitive`, `ambience`, ...).

    Non-v2.1 records (v1, v2.0) are returned unchanged. Google values come
    only from `quarantine` and only when `policy == demo_phi_thuong_mai`.
    The legacy `verified` flag is replaced by the eligibility rule (WP4):
    status active, not a trip base, hours known.
    """
    if not is_v21(poi):
        return poi
    policy = policy or google_policy()
    demo = policy == "demo_phi_thuong_mai"
    q = (quarantine or {}).get(poi["poi_id"], {}) if demo else {}
    v = dict(poi)
    cat = poi.get("category")
    hours = poi.get("hours") or {}
    tags = poi.get("tags") or {}
    price = poi.get("price") or {}
    prov = poi.get("provenance") or {}

    open_ = list(hours.get("open") or [])
    if demo and hours.get("kind") != "fixed" and q.get("hours_open"):
        open_ = list(q["hours_open"])          # Google every-day hours (demo only)
    v["opening_hours"] = [", ".join(open_)] if open_ else []

    dwell = poi.get("dwell") or {}
    v["visit_min"] = {k: dwell.get(k) for k in ("p25", "p50", "p75")}
    dprov = prov.get("dwell") or {}
    v["dur_source"] = "human" if dprov.get("verified_by") in ("user", "human") else "category_rule"
    dconf = dprov.get("confidence") or 0
    v["dur_confidence"] = "high" if dconf >= 0.7 else ("medium" if dconf >= 0.5 else "low")

    tier = price.get("tier")
    st = {_TAG_RENAME_BACK.get(k, k): val for k, val in tags.items() if k not in _TAG_NOT_SMART}
    if tier in ("cheap", "medium", "expensive"):
        st["price_band"] = tier
        st["band_source"] = (prov.get("price") or {}).get("verified_by")
    v["smart_tags"] = st
    v["free_entry"] = True if tier in ("free", "included") else None
    v["intensity"] = tags.get("effort") if tags.get("effort") is not None else 2
    v["weather_sensitive"] = bool(tags.get("weather_sensitive"))

    v["cat"] = legacy_cat(cat, hours.get("archetype"))
    v["type"] = q.get("type") or LEGACY_TYPE_VI.get(cat, cat)
    v["tags"] = list(q.get("tags_v1") or []) or [LEGACY_TYPE_VI.get(cat, cat)]
    # WP6: legacy `rating` (0-5 scale the rankers read) comes from the clean
    # `popularity.prize_prior` as 3 + 2*prior, so the existing thresholds
    # (4.5 "rating cao", experience fit floor 3.0) keep their meaning. Only the
    # demo policy may show the quarantined Google rating instead.
    prior = (poi.get("popularity") or {}).get("prize_prior")
    v["prize_prior"] = prior
    v["rating"] = q.get("rating") or (round(3.0 + 2.0 * prior, 2) if prior is not None else None)
    v["price_level"] = q.get("price_level") or TIER_RANK.get(tier, 2)
    v["ambience"] = q.get("ambience") or ""
    v["pros"] = list(q.get("pros") or [])
    v["cons"] = list(q.get("cons") or [])
    v["verified"] = (poi.get("status") == "active" and poi.get("role") != "base"
                     and hours.get("kind") != "unknown")
    v["source"] = (prov.get("location") or {}).get("source") or "danang-v2.1"
    v["fetched_at"] = poi.get("valid_from")
    return v


def view_pois(pois: list[dict], snapshot_dir: str | None = None,
              policy: str | None = None) -> list[dict]:
    """Apply `poi_view` to a POI list (quarantine read from the snapshot)."""
    if not any(is_v21(p) for p in pois):
        return pois
    q = load_quarantine(snapshot_dir)
    return [poi_view(p, policy, q) for p in pois]


def matrix_path(snapshot_dir: str) -> str:
    """Path of the snapshot's matrix.json.

    A snapshot may hold `matrix_ref.json` ({"matrix_from": "<relative path>"})
    instead of its own copy when its poi_ids are identical to another
    snapshot's (danang-v2 reuses danang-v1's 26 MB matrix).
    """
    own = os.path.join(snapshot_dir, "matrix.json")
    ref = os.path.join(snapshot_dir, "matrix_ref.json")
    if not os.path.exists(own) and os.path.exists(ref):
        target = load_json(ref).get("matrix_from", "")
        return os.path.normpath(os.path.join(snapshot_dir, target))
    return own


def load_matrix_cells(snapshot_dir: str) -> dict:
    """Read the snapshot's matrix (see `matrix_path`) -> cells dict."""
    return load_json(matrix_path(snapshot_dir))["cells"]
