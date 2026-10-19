"""SerpApi Google Maps fetch (T003b-SCRIPT, lane A).

The normal run resumes the search cache in <raw>/search/. ``--refresh``
uses a month-specific search cache so a new month's run fetches fresh
results while retries in that month resume without re-spending. Results
are normalized from search payloads. Do not call the details endpoint:
google_maps with q=place_id returned "Google hasn't returned any results"
in the live 2026-09-28 check (20 quota spent learning this).

QUOTA GUARD (hard): free 250 searches/month -> STOP at 240. Counter is
persisted in <raw>/quota.json; every HTTP call checks first, increments
after, and cached responses do not spend quota. Exceeding raises
QuotaExceeded (exit 3), never silently.

KEY: env SERPAPI_KEY only (see docs/serpapi-quota.md). Never hardcoded
or logged (URLs are logged with api_key redacted). No key -> exit 2.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import date

API = "https://serpapi.com/search.json"
QUOTA_CAP = 240

try:  # Windows cp1252 console can't print Vietnamese queries otherwise
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:  # noqa: BLE001
    pass

CATEGORIES = ["nhà hàng", "quán cà phê", "khu du lịch",
              "bảo tàng", "bãi biển", "chợ"]
DISTRICTS = ["Hải Châu", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu", "Thanh Khê"]
# quota math: 6 x 5 = 30 searches + <=200 details = <=230 (buffer 10).
DN_BBOX = (15.9, 107.9, 16.25, 108.45)  # south, west, north, east; Sep bulk filter


class QuotaExceeded(RuntimeError):
    pass


def _load_dotenv(path: str = "BE/.env") -> None:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


class QuotaTracker:
    def __init__(self, raw_dir: str, cap: int = QUOTA_CAP):
        self.path = os.path.join(raw_dir, "quota.json")
        self.cap = cap
        self.used = 0
        if os.path.exists(self.path):
            self.used = int(json.load(open(self.path, encoding="utf-8"))["used"])

    def check(self) -> None:
        if self.used >= self.cap:
            raise QuotaExceeded(f"quota cap {self.cap} reached (used {self.used})")

    def spend(self, what: str) -> None:
        self.used += 1
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        json.dump({"used": self.used, "last": what, "cap": self.cap},
                  open(self.path, "w", encoding="utf-8"))
        print(f"quota {self.used}/{self.cap}: {what}")


def _get(params: dict, key: str, quota: QuotaTracker, what: str,
         transport=None) -> dict:
    quota.check()
    if transport is not None:
        data = transport(params)
    else:
        import urllib.error
        params = {**params, "api_key": key}  # key only on the wire, never logged
        url = API + "?" + urllib.parse.urlencode(params)
        logged = url.replace(key, "***")
        print(f"GET {logged[:160]}")
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("DUNG NGAY: 401 Unauthorized — SERPAPI_KEY sai/het han. "
                      "Khong retry. Lay key moi o serpapi.com/manage-api-key, "
                      "cap nhat BE/.env (khong commit).")
                raise SystemExit(4)
            raise
    quota.spend(what)
    return data


def search_params(category: str, district: str) -> dict:
    return {"engine": "google_maps", "type": "search",
            "q": f"{category} {district} Đà Nẵng", "hl": "vi", "gl": "vn"}


def details_params(place_id: str) -> dict:
    # DOCUMENTATION ONLY — live-verified 2026-09-28 that SerpApi
    # google_maps does NOT serve place details this way (returns
    # "Google hasn't returned any results"). Kept so nobody retries it.
    # run() normalizes from the (rich) search payload instead.
    return {"engine": "google_maps", "q": place_id, "hl": "vi", "gl": "vn"}


def raw_path(raw_dir: str, kind: str, key: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in key)[:80]
    return os.path.join(raw_dir, kind, safe + ".json")


def cached_or_fetch(path: str, params: dict, key: str, quota: QuotaTracker,
                    what: str, transport=None) -> dict:
    if os.path.exists(path):
        print(f"resume (no quota): {path}")
        return json.load(open(path, encoding="utf-8"))
    data = _get(params, key, quota, what, transport)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return data


def collect_ids(raw_dir: str, key: str, quota: QuotaTracker,
                transport=None, max_queries: int = 0,
                search_cache_kind: str = "search") -> dict:
    """Search all queries; return {place_id: first-seen search item}."""
    queries = [(c, d) for c in CATEGORIES for d in DISTRICTS]
    if max_queries:
        queries = queries[:max_queries]
    items: dict[str, dict] = {}
    for cat, dist in queries:
        q = f"{cat} {dist}"
        data = cached_or_fetch(raw_path(raw_dir, search_cache_kind, q),
                               search_params(cat, dist), key, quota,
                               f"search: {q}", transport)
        for item in data.get("local_results", []):
            pid = item.get("place_id") or item.get("data_id")
            if pid and pid not in items:
                items[pid] = item
    print(f"collected {len(items)} unique place_ids from {len(queries)} queries")
    return items


def parse_hours(op_hours) -> list[str]:
    """Day-keyed SerpApi hours -> ["HH:MM-HH:MM"] (uniform) or distinct list."""
    if isinstance(op_hours, list):
        return [h for h in op_hours if isinstance(h, str) and "-" in h]
    if not isinstance(op_hours, dict):
        return []
    ranges = set()
    for v in op_hours.values():
        s = str(v).replace("–", "-").replace("—", "-")
        if "-" in s and ":" in s:
            ranges.add(s.strip())
    if len(ranges) == 1:
        return sorted(ranges)
    return sorted(ranges)  # non-uniform: keep distinct (human pass refines)


def normalize(place_id: str, search_item: dict) -> dict:
    """SerpApi search payload -> TravelEval POI (21 keys, cf. seed pois.json)."""
    title = search_item.get("title", "")
    gps = search_item.get("gps_coordinates") or {}
    cats = search_item.get("types") or search_item.get("categories") or []
    today = date.today().isoformat()
    rating = search_item.get("rating")
    return {
        "poi_id": place_id, "name": title,
        "type": cats[0] if cats else "unknown",
        "lat": (gps or {}).get("latitude"), "lon": (gps or {}).get("longitude"),
        "opening_hours": parse_hours(search_item.get("operating_hours")),
        "visit_min": {"p25": 0, "p50": 0, "p75": 0},  # nac-2 fills later
        "dur_source": "pending_llm", "dur_confidence": "low",
        "price_level": 2, "fee": 0,
        "rating": rating,
        "tags": cats,
        "intensity": 2, "ambience": "", "weather_sensitive": False,
        "pros": [], "cons": [],
        "source": "serpapi/google-maps", "fetched_at": today,
        "verified": False,  # human spot-check 15% flips to true (T003b)
    }


def inside_danang_bbox(lat, lon) -> bool:
    """Return true only for geocoded coordinates inside the Sep bulk bbox."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False
    south, west, north, east = DN_BBOX
    return south <= lat <= north and west <= lon <= east


def _load_pois(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    value = json.load(open(path, encoding="utf-8"))
    if isinstance(value, dict):  # also accept the published snapshot envelope
        value = value.get("pois", [])
    if not isinstance(value, list):
        raise ValueError(f"expected POI array in {path}")
    return [poi for poi in value if isinstance(poi, dict)]


def merge_refresh(previous: list[dict], items: dict[str, dict]) -> tuple[list[dict], dict]:
    """Refresh known fields and append new Da Nang POIs without losing others."""
    pois = []
    by_id = {}
    for poi in previous:
        if not inside_danang_bbox(poi.get("lat"), poi.get("lon")):
            continue
        saved = dict(poi)
        pid = saved.get("poi_id")
        if pid and pid not in by_id:
            by_id[pid] = saved
            pois.append(saved)

    new_place_ids = []
    changed_hours = []
    changed_ratings = []
    changed_coords = []
    excluded_outside_bbox = 0
    today = date.today().isoformat()

    for pid, item in items.items():
        gps = item.get("gps_coordinates") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        if not inside_danang_bbox(lat, lon):
            excluded_outside_bbox += 1
            continue

        fresh = normalize(pid, item)
        existing = by_id.get(pid)
        if existing is None:
            by_id[pid] = fresh
            pois.append(fresh)
            new_place_ids.append(pid)
            continue

        old_hours = existing.get("opening_hours") or []
        if fresh["opening_hours"] and fresh["opening_hours"] != old_hours:
            changed_hours.append({
                "place_id": pid, "from": old_hours,
                "to": fresh["opening_hours"],
            })
            existing["opening_hours"] = fresh["opening_hours"]

        old_rating = existing.get("rating")
        if fresh["rating"] is not None and fresh["rating"] != old_rating:
            changed_ratings.append({
                "place_id": pid, "from": old_rating,
                "to": fresh["rating"],
            })
            existing["rating"] = fresh["rating"]

        old_lat, old_lon = existing.get("lat"), existing.get("lon")
        if lat != old_lat or lon != old_lon:
            changed_coords.append({
                "place_id": pid,
                "from": {"lat": old_lat, "lon": old_lon},
                "to": {"lat": lat, "lon": lon},
            })
            existing["lat"], existing["lon"] = lat, lon

        existing["fetched_at"] = today

    delta = {
        "new_place_ids": new_place_ids,
        "changed_hours": changed_hours,
        "changed_ratings": changed_ratings,
        "changed_coords": changed_coords,
        "quota_spent": 0,
        "total_pois": len(pois),
        "excluded_outside_bbox": excluded_outside_bbox,
    }
    return pois, delta


def run(raw_dir: str, key: str, max_queries: int = 0,
        transport=None, refresh: bool = False) -> list[dict]:
    os.makedirs(raw_dir, exist_ok=True)
    quota = QuotaTracker(raw_dir)
    month = date.today().strftime("%Y-%m")
    if refresh:
        # Keep the initial raw stable so a completed or resumed refresh can
        # always produce the same delta, even after pois_raw.json is replaced.
        baseline_path = os.path.join(raw_dir, f"pois_raw_before_{month}.json")
        current_raw_path = os.path.join(raw_dir, "pois_raw.json")
        if not os.path.exists(baseline_path):
            if os.path.exists(current_raw_path):
                shutil.copyfile(current_raw_path, baseline_path)
            else:
                json.dump([], open(baseline_path, "w", encoding="utf-8"))

        items = collect_ids(raw_dir, key, quota, transport, max_queries,
                            search_cache_kind=os.path.join("search", month))
        if max_queries:
            in_bbox = sum(
                inside_danang_bbox(
                    (item.get("gps_coordinates") or {}).get("latitude"),
                    (item.get("gps_coordinates") or {}).get("longitude"),
                )
                for item in items.values()
            )
            print(f"refresh trial only: {in_bbox} in-bbox results; final raw unchanged")
            return [normalize(pid, item) for pid, item in items.items()
                    if inside_danang_bbox(
                        (item.get("gps_coordinates") or {}).get("latitude"),
                        (item.get("gps_coordinates") or {}).get("longitude"),
                    )]

        previous = _load_pois(baseline_path)
        pois, delta = merge_refresh(previous, items)
        delta["quota_spent"] = quota.used  # monthly quota.json was reset before refresh
        raw_pathname = os.path.join(raw_dir, "pois_raw.json")
        with open(raw_pathname, "w", encoding="utf-8") as f:
            json.dump(pois, f, ensure_ascii=False, indent=1)
        summary_path = os.path.join(raw_dir, f"refresh-{month}.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(delta, f, ensure_ascii=False, indent=2)
        print(f"wrote {len(pois)} refreshed raw POIs; delta {summary_path}; "
              f"quota used {quota.used}/{QUOTA_CAP}")
        return pois

    items = collect_ids(raw_dir, key, quota, transport, max_queries)
    pois = [normalize(pid, item) for pid, item in items.items()]
    with open(os.path.join(raw_dir, "pois_raw.json"), "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(pois)} raw POIs; quota used {quota.used}/{QUOTA_CAP}")
    return pois


def selftest() -> int:
    """Mock end-to-end (no network, no key): search->normalize->quota."""
    import tempfile
    calls: list[dict] = []

    def mock(params: dict) -> dict:
        calls.append(params)
        q = params["q"]
        return {"local_results": [
            {"place_id": f"pid-{q}-1", "title": f"Place {q} 1",
             "rating": 4.5, "types": ["restaurant"],
             "operating_hours": {"x": "06:00–23:00"},
             "gps_coordinates": {"latitude": 16.0, "longitude": 108.2}},
            {"place_id": f"pid-{q}-2", "title": f"Place {q} 2",
             "rating": 4.0, "types": ["cafe"],
             "gps_coordinates": {"latitude": 16.1, "longitude": 108.3}}]}

    tmp = tempfile.mkdtemp(prefix="serp_")
    pois = run(tmp, key="MOCK", max_queries=2, transport=mock)
    assert len(pois) == 4, pois
    assert all(set(p) >= {"poi_id", "visit_min", "dur_source", "verified"} for p in pois)
    assert all(p["dur_source"] == "pending_llm" and p["verified"] is False for p in pois)
    assert pois[0]["opening_hours"] == ["06:00-23:00"], pois[0]["opening_hours"]
    assert pois[0]["lat"] == 16.0 and pois[0]["rating"] == 4.5
    q = QuotaTracker(tmp)
    assert q.used == 2, q.used  # search-only: 2 searches, 0 details
    # resume spends nothing
    before = q.used
    run(tmp, key="MOCK", max_queries=2, transport=mock)
    assert QuotaTracker(tmp).used == before, "resume must not re-spend"
    # cap enforced
    q2 = QuotaTracker(tmp, cap=before)
    try:
        q2.check()
        raise SystemExit("FAIL: cap not enforced")
    except QuotaExceeded:
        pass
    print(f"selftest OK: {len(pois)} pois, quota {before}, resume+cap enforced")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T003b SerpApi fetch (key needed for live)")
    ap.add_argument("--raw", default="data/snapshots/danang-full-tmp/")
    ap.add_argument("--max-queries", type=int, default=0)
    ap.add_argument("--refresh", action="store_true",
                    help="fresh month-specific search cache + filtered delta")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    _load_dotenv()
    key = os.environ.get("SERPAPI_KEY", "")
    if not key:
        print("THIEU SERPAPI_KEY: console https://serpapi.com/manage-api-key -> "
              "copy key -> BE/.env them dong SERPAPI_KEY=... (khong commit). "
              "Xem docs/serpapi-quota.md. DUNG o day, khong chay bulk.")
        return 2
    try:
        run(args.raw, key, args.max_queries, refresh=args.refresh)
    except QuotaExceeded as e:
        print(f"DUNG: {e} (resume sau khi quota reset / cache giu nguyen)")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
