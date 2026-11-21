"""Shared stdlib glue for BE (one spot for copy-pasted helpers).

Time <-> minutes, opening-hours parsing, plan fee/deadline and JSON/snapshot
reads, shared by the app services, `eval/` and `ml/`. No config, no classes, no
third-party imports (DoD).
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any


def to_int(value, default: int = 2) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def to_min(hhmm: str) -> int:
    """'HH:MM' -> minutes since midnight (well-formed input assumed)."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmm(minutes: int) -> str:
    """Minutes since midnight -> 'HH:MM'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


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


DAY_MIN = 24 * 60


def day_spans(spec: str) -> list[tuple[int, int]]:
    """Sorted, merged open spans of one hours element on a same-day clock.

    A span that closes at or before it opens runs past midnight, so its close
    moves to the next day ("19:30-03:00" -> 1170..1620, "09:00-00:00" ->
    540..1440). A day trip never uses the early-morning tail of the previous
    evening, so that tail is not modelled here (`in_range` still accepts it).
    """
    spans = sorted((o, c if c > o else c + DAY_MIN) for o, c in _intervals(spec))
    merged: list[tuple[int, int]] = []
    for o, c in spans:
        if merged and o <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], c))
        else:
            merged.append((o, c))
    return merged



def parse_windows(hours: list | None) -> list[tuple[int, int]]:
    """Every 'HH:MM-HH:MM' window of `hours` as same-day minutes, sorted.

    A window that wraps midnight ("17:00-02:00") or ends at "23:59" is
    clipped to the end of the day (1440): a day plan never crosses midnight.
    The optimizer chooses one of these (danang-v2.1 multi-window hours, WP3).
    """
    out = []
    for spec in hours or []:
        for o, c in _intervals(spec):
            if c <= o or c >= 23 * 60 + 59:
                c = 24 * 60
            out.append((o, c))
    return sorted(set(out))

def open_windows(hours: list | None) -> list[tuple[int, int]] | None:
    """Same-day open windows that every listed variant agrees on.

    Each `opening_hours` element is one variant of the week: the crawl keeps
    the distinct weekday ranges, e.g. ["10:30-14:00, 17:30-20:45",
    "17:30-20:45"] = lunch closed on some days. The trip weekday is not
    matched to them, so the safe answer is the intersection (open on every
    variant). None = no parsable hours (caller picks the default); [] = the
    variants share no open time.
    """
    variants = [s for s in (day_spans(h) for h in hours or []) if s]
    if not variants:
        return None
    common = variants[0]
    for spans in variants[1:]:
        common = [(max(a, c), min(b, d)) for a, b in common for c, d in spans
                  if max(a, c) < min(b, d)]
    return sorted(common)


# Hours assumed for a POI that has none, so a missing value never reads as
# "open all trip" (a pagoda at 23:05). Each entry is the 15-minute slots in
# which >= SAFE_HOURS_SHARE of that group's POIs with sourced hours are open,
# measured on danang-v1 by `BE/ml/data/normalize_fields.py --safe-hours`
# (test_normalize_fields fails when the table drifts from the snapshot).
# Sightseeing categories are pooled (too few rows each). [] = no such time
# (markets mix dawn wet markets with night markets): not schedulable until
# real hours land. Other groups (lodging, transport) keep the trip window.
SAFE_HOURS_SHARE = 0.9
SIGHTSEEING_CATS = ("attraction", "beach", "landmark", "museum", "nature", "park",
                    "temple", "viewpoint")
SAFE_HOURS: dict[str, list[str]] = {
    "bar": ["19:30-23:45"],
    "cafe": ["07:30-19:30"],
    "market": [],
    "restaurant": ["17:00-21:00"],
    "sightseeing": ["08:30-17:00"],
    "spa": ["09:30-19:30"],
}


def hours_group(cat: str) -> str:
    """SAFE_HOURS key of a category ("" when it has no assumed hours)."""
    if cat in SIGHTSEEING_CATS:
        return "sightseeing"
    if cat == "shop":  # measured with the markets: both were one category
        return "market"
    return cat if cat in ("restaurant", "cafe", "bar", "spa", "market") else ""


def poi_open_windows(poi: dict) -> list[tuple[int, int]] | None:
    """`open_windows` of the POI's hours, else of its group's SAFE_HOURS.

    None = neither (the caller keeps its default, e.g. the trip window for a
    legacy fixture without `cat`); [] = no time is safe to schedule, which is
    also a POI closed on the trip's date (`poi_on_date`).
    """
    if poi.get("closed_today"):
        return []
    wins = open_windows(poi.get("opening_hours"))
    if wins is not None:
        return wins
    safe = SAFE_HOURS.get(hours_group(poi.get("cat") or ""))
    if safe is None:
        return None
    return open_windows(safe) or []


def iso_date(date: str | None, offset: int = 0) -> str:
    """The ISO date `offset` days after `date`; "" without a usable ISO date."""
    try:
        start = datetime.date.fromisoformat(date or "")
    except (TypeError, ValueError):
        return ""
    return (start + datetime.timedelta(days=offset)).isoformat()


def weekday_of(date: str | None) -> int | None:
    """Monday = 0, as `hours_by_day` is stored; None without a usable ISO date."""
    day = iso_date(date)
    return datetime.date.fromisoformat(day).weekday() if day else None


def poi_on_date(poi: dict, date: str | None) -> dict:
    """The POI as it is on that date: that weekday's hours, or `closed_today`.

    Everything downstream reads `opening_hours`, so this one projection is the
    whole weekday logic. No date or no weekly table leaves the POI as it is
    (`open_windows` then takes what every variant of the week agrees on).
    """
    day = weekday_of(date)
    week = poi.get("hours_by_day")
    if day is None or not week:
        return poi
    today = week[day]
    return {**poi, "opening_hours": [today] if today else [], "closed_today": not today}


def closed_weekdays(poi: dict) -> list[int]:
    """Weekdays (Monday = 0) the weekly table says the POI is closed."""
    return [day for day, hours in enumerate(poi.get("hours_by_day") or []) if not hours]


def parse_hours(hours: list | None) -> tuple[int, int] | None:
    """First window of `open_windows` as minutes, or None when unset.

    Variants that share no open time give (0, 0): nothing fits, rather than
    the caller's "open all trip" default.
    """
    windows = open_windows(hours)
    if windows is None:
        return None
    return windows[0] if windows else (0, 0)


# Price level assumed for a POI with no price evidence (`price_level` null):
# the middle band, which is what the crawl placeholder 2 used to say
# silently. Ranking is unchanged; retrieval labels the price as unverified.
UNKNOWN_PRICE_LEVEL = 2


def price_level_of(poi: dict) -> int:
    """POI price level 1..3, UNKNOWN_PRICE_LEVEL when null or absent."""
    level = poi.get("price_level")
    return UNKNOWN_PRICE_LEVEL if level is None else int(level)


# Rating shrunk towards the pool by its review count (a Bayesian average): a 5.0
# from 2 reviews says little, a 4.9 from 10,000 says a lot. Scoring on the raw
# rating fills a rating-first day with the least-known 5.0 places. The prior sits
# near the verified pool's mean rating, its weight near their median review count
# (4.56 and 216 on danang-v1, Google Maps 30/10/2026).
RATING_PRIOR = 4.5
RATING_PRIOR_REVIEWS = 200
# Below this a rating is an anecdote, not evidence (never "rating cao").
FEW_REVIEWS = 20


def trusted_rating(poi: dict) -> float:
    """Rating to score on: the raw rating when the review count is unknown
    (fixtures, fresh crawls); no rating stays 0, not the prior."""
    rating = float(poi.get("rating") or 0.0)
    reviews = poi.get("review_count")
    if not rating or reviews is None:
        return rating
    return round((reviews * rating + RATING_PRIOR_REVIEWS * RATING_PRIOR)
                 / (reviews + RATING_PRIOR_REVIEWS), 3)


# What one person spends at a POI with no known ticket: the middle of its price
# band (under 100k, 100-500k, over 500k per person).
BAND_FEE_VND = {"cheap": 50_000, "medium": 300_000, "expensive": 700_000}
# The band is one scale for a meal. A drink or a small purchase in the same band
# costs far less: 300k for a coffee was the visible error of the old table.
BAND_FEE_BY_CAT = {
    "cafe": {"medium": 100_000, "expensive": 200_000},
    "bar": {"medium": 200_000, "expensive": 400_000},
    "shop": {"medium": 100_000, "expensive": 200_000},
}
# Open access: a cheap band here means free to enter, not a cheap meal.
FREE_ENTRY_CATS = frozenset({"beach", "landmark", "nature", "park", "temple", "viewpoint"})
# A place the review found no ticket for costs nothing to enter, whatever its band.
NO_TICKET_FREE_CATS = FREE_ENTRY_CATS | {"museum"}


def effective_fee(poi: dict) -> int | None:
    """VND one person spends here: the ticket, else the middle of the price band,
    0 for an open-access place with no ticket. None = price unknown, never "free".
    A POI with no smart_tags (fixtures) has no band to read and keeps its `fee`."""
    price = poi.get("price")
    if isinstance(price, dict) and "tier" in price:
        # v2.1 (WP2): one field, 4 tiers (+ included = paid via the parent ticket).
        return TIER_MIDPOINT.get(price.get("tier"))
    ticket = poi.get("ticket_vnd")
    if isinstance(ticket, int):
        return ticket
    fee = int(poi.get("fee") or 0)
    tags = poi.get("smart_tags")
    if fee > 0 or tags is None:
        return fee
    band, cat = tags.get("price_band"), poi.get("cat")
    if band == "cheap" and cat in FREE_ENTRY_CATS and tags.get("ticket") is not True:
        return 0
    if cat in NO_TICKET_FREE_CATS and tags.get("ticket") is False:
        return 0
    return BAND_FEE_BY_CAT.get(cat, {}).get(band) or BAND_FEE_VND.get(band)


def fee_is_estimate(poi: dict) -> bool:
    """True when `effective_fee` comes from the price band, not from a real price."""
    return bool(effective_fee(poi)) and not isinstance(poi.get("ticket_vnd"), int) \
        and not int(poi.get("fee") or 0)


def party_size(trip: dict) -> int:
    """People the budget covers (POI prices are per person)."""
    return max(1, int(trip.get("travelers") or 1))


def total_fee(acts: list[dict], pois: dict, travelers: int = 1) -> int:
    """What the party spends at these stops (unknown POI or price counts 0)."""
    return travelers * sum(effective_fee(pois.get(a.get("poi_id"), {}) or {}) or 0
                           for a in acts)


def plan_cost(itinerary: dict, pois: dict, travelers: int = 1) -> int:
    """Itinerary cost: explicit `total_cost` wins, else what the party spends."""
    if "total_cost" in itinerary:
        return int(itinerary["total_cost"])
    return total_fee(itinerary.get("activities", []), pois, travelers)


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

WEEKDAYS_V21 = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")   # hours.closed_days codes

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
    # closed_days (Mo..Su) -> the weekly table main's weekday logic reads
    # (`hours_by_day`, Monday = 0, "" = closed; `poi_on_date` -> closed_today)
    closed = set(hours.get("closed_days") or [])
    if closed and open_:
        day = ", ".join(open_)
        v["hours_by_day"] = ["" if d in closed else day for d in WEEKDAYS_V21]

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


def load_matrix_cells(snapshot_dir: str):
    """<snapshot_dir>/matrix.json -> cells Mapping (legacy dict or dense-v1).

    Raises FileNotFoundError like before when the snapshot has no matrix.
    """
    from BE.app.services.matrix import load_matrix_doc
    return load_matrix_doc(os.path.join(snapshot_dir, "matrix.json"))["cells"]
