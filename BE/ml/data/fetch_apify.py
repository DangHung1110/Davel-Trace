"""Fetch full Da Nang snapshot via Apify one-shot (T003b, CHUAN BI - CHUA CHAY).

Trang thai: script + huong dan xong, token CHUA CO -> KHONG chay bulk.
Khi co token, orchestrator giao lenh chay moi chay (test 10 truoc, <=2 ngay).

== Lay token (5 phut, mien phi $5/thang) ==
1. Mo https://console.apify.com/ -> Sign up (Google/GitHub).
2. Settings -> Integrations -> API tokens -> Create -> copy token `apify_api_...`.
3. Tao file BE/.env (KHONG commit) voi 1 dong:
       APIFY_TOKEN=apify_api_...paste-token...
   (Loader .env do lane C tao o T004; script nay doc ca env var co san.)
4. Chay thu 10 POIs:
       python BE/ml/data/fetch_apify.py --max 10 --out data/snapshots/danang-full-tmp/
   Kiem tra 10 ban ghi dat chuan schema -> moi chay bulk:
       python BE/ml/data/fetch_apify.py --max 200 --out data/snapshots/danang-full-tmp/
5. Human spot-check 15% + normalize -> thay pois.json (T003b xong).

== Actor ==
`apify/google-maps-scraper`, input: locationQuery "Da Nang, Vietnam",
searchStrings ["khu du lich Da Nang", "nha hang Da Nang", "quan an Da Nang",
"bao tang Da Nang", "bai bien Da Nang"], maxCrawledPlacesPerSearch=<max>,
reviews/enrichment OFF (tiet kiem free quota, dung R7).

Chi dung stdlib (urllib) de khong them dependency moi (DoD).
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date

ACTOR = "apify/google-maps-scraper"
API = "https://api.apify.com/v2"
SEARCH_STRINGS = [
    "khu du lich Da Nang",
    "nha hang Da Nang",
    "quan an Da Nang",
    "bao tang Da Nang",
    "bai bien Da Nang",
]


def _load_dotenv(path: str = "BE/.env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _api(path: str, token: str, data: dict | None = None, timeout: int = 60) -> dict:
    url = f"{API}{path}?token={urllib.parse.quote(token)}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def normalize(item: dict) -> dict:
    """Apify Google-Maps-Scraper item -> TravelEval POI schema (data-model.md)."""
    lat = (item.get("location") or {}).get("lat")
    lng = (item.get("location") or {}).get("lng")
    cats = item.get("categories") or []
    return {
        "poi_id": item.get("placeId") or item.get("url") or item.get("title", ""),
        "name": item.get("title", ""),
        "type": (cats[0] if cats else "unknown"),
        "lat": lat,
        "lon": lng,
        "opening_hours": [],
        "visit_min": {"p25": 0, "p50": 0, "p75": 0},  # T003c nac-2 dien sau
        "dur_source": "pending_llm",
        "dur_confidence": "low",
        "price_level": item.get("priceLevel"),
        "fee": 0,
        "rating": item.get("totalScore"),
        "tags": cats,
        "intensity": 2,
        "ambience": "",
        "weather_sensitive": False,
        "pros": [],
        "cons": [],
        "source": "apify/google-maps-scraper",
        "fetched_at": date.today().isoformat(),
        "verified": False,  # human spot-check 15% moi flip true (T003b)
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Apify one-shot fetch (T003b)")
    ap.add_argument("--max", type=int, default=10)
    ap.add_argument("--out", default="data/snapshots/danang-full-tmp/")
    args = ap.parse_args()

    _load_dotenv()
    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        print("THIEU APIFY_TOKEN: xem huong dan lay token o docstring script nay, "
              "ghi vao BE/.env (khong commit). DUNG o day, khong chay bulk.")
        return 2

    run = _api(f"/acts/{ACTOR}/runs", token, {
        "searchStringsArray": SEARCH_STRINGS,
        "locationQuery": "Da Nang, Vietnam",
        "maxCrawledPlacesPerSearch": max(1, args.max // len(SEARCH_STRINGS)),
        "includeReviews": False,
        "includeImages": False,
    })
    run_id = run["data"]["id"]
    print(f"run started: {run_id}, polling...")
    while True:
        st = _api(f"/actor-runs/{run_id}", token)["data"]["status"]
        if st in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            print(f"run {st}")
            if st != "SUCCEEDED":
                return 1
            break
        time.sleep(10)

    ds = _api(f"/actor-runs/{run_id}", token)["data"]["defaultDatasetId"]
    items = _api(f"/datasets/{ds}/items?limit={args.max}", token)
    pois = [normalize(it) for it in items]
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "pois_raw.json"), "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(pois)} raw POIs -> {args.out}pois_raw.json "
          "(tiep: normalize tay + spot-check 15% + nac-2 duration)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
