"""Final curation of snapshot `danang-v2` (format v2.3, 19/11/2026).

Called by `migrate_v2.py` after every record is built. Keeps only the POIs a
day plan can use and writes the rest to `dropped.json` with one reason each.

The user's rule (19/11/2026): prices may be approximate; a POI without enough
information on Google Maps may be dropped; the machine decides everything it
can. So no POI is dropped for its price (category estimates are allowed), and
every question the v2.2 review form asked a human is decided here by rule.
A later `decisions_*.json` from a human still wins: a POI the user set active
is never dropped by these rules.

Google values only DECIDE keep/drop. They never enter `pois.json`; they stay in
`quarantine_google.json`.

Reasons, first match wins:

  excluded        already excluded (v1 review, v1 plan_tier, v2 name rules, user)
  lodging         a hotel: the app never plans lodging; the trip start comes from the map
  review          a POI the build could not classify (decided below)
  closed          Google Maps says permanently / temporarily closed
  not_listed      Google Maps has no listing (v1 review)
  few_reviews     fewer than MIN_REVIEWS reviews on Google Maps, or a local-only
                  place whose review count was never read (signature POIs exempt)
  no_hours        a business with no opening hours on Google Maps nor any other source
  hours_conflict  its Google hours contradict every hour group of its category
  duplicate       the same place as another kept POI
"""

from __future__ import annotations

import difflib
import re

import v2_rules as R

MIN_REVIEWS = 30
# Places whose visit depends on opening hours. Public places (beach, viewpoint,
# outdoor landmark, temple) are open-access and use the rule windows instead.
COMMERCIAL = ("restaurant", "cafe", "nightlife", "wellness", "day_market",
              "night_market", "paid_attraction", "museum_indoor")
REASONS = {
    "excluded": None,     # keeps the reason already written by the build
    "lodging": "lưu trú — app không xếp khách sạn vào lịch; điểm xuất phát lấy từ bản đồ",
    "review": None,
    "closed": "Google Maps: đã đóng cửa",
    "closed_permanently": "Google Maps: đã đóng cửa vĩnh viễn",
    "closed_temporarily": "Google Maps: đang tạm đóng cửa",
    "not_listed": "không tìm thấy trên Google Maps",
    "few_reviews": f"ít thông tin trên Google Maps (chưa đủ {MIN_REVIEWS} lượt đánh giá)",
    "few_reviews_local": "điểm của người địa phương, Google Maps không có số đánh giá",
    "no_hours": "không có giờ mở cửa trên Google Maps hay nguồn nào khác",
    "no_hours_osm": "không có giờ mở cửa ở nguồn nào (OSM, web); chưa đối chiếu được Google Maps",
    "hours_conflict": "giờ trên Google Maps lệch hẳn mọi nhóm giờ của thể loại",
    "duplicate": "trùng với '{}'",
}
RULES = ("excluded", "lodging", "review", "closed", "not_listed", "few_reviews",
         "no_hours", "hours_conflict", "duplicate")
# The one POI left in `review` by the v2 rules (machine decision 19/11/2026).
REVIEW_DECISIONS = {
    "osm:node/1623183649": "đỉnh núi OSM, không có lối tham quan riêng — đã có Bán đảo Sơn Trà và Đỉnh Bàn Cờ",
}
# Display names that fail gate G5 (`|`, Korean/Chinese/Japanese, > 60 chars),
# cleaned by hand-checked proposals; the source name stays in `name_raw`.
NAME_FIXES = {
    "ChIJZSsvT9QZQjERf-oLnsT1C3Y": "Yen Yakiniku & Izakaya",
    "ChIJHfGPsJkXQjERsHCXRTXX_Xs": "Nhà hàng Hàn Quốc lòng bò nướng",
    "ChIJeaPwiDUYQjERt4yUm81Oqi8": "Khu ẩm thực Chợ Cồn",
    "osm:node/13677406601": "Đài tưởng niệm chuyến bay 229 (1979)",
    "ChIJs3Rt4-QZQjERPTSZ7G6XAK0": "Clover Spa",
    "ChIJv1gepxMZQjER2xJtkXvi9xU": "Jeju Spa – Massage & Nail",
    "ChIJpRFvp6sZQjERY_CDfnMCx2w": "Vigift Đà Nẵng – Quà Đặc Sản",
    "ChIJM1DTVHkZQjERDW1JNclcAtw": "Massage người mù Đức Quý",
    "ChIJn9Kkxh4ZQjERgDXEcvzD4nI": "MarLan Pub",
    "ChIJu9GUjOgZQjERpfx8z-GIMEw": "Kết Bar",
    "ChIJxRB4CRgXQjER6zy0em0FyTk": "Oppa O Bar",
    "ChIJW9b8Ky0XQjERPn8CJNdE0Lk": "Chùa Mỹ Thị",
    "ChIJ8e-HnOoZQjER1tLf4hD65xI": "Elsa Spa",
    "ChIJp9cNzfwZQjERS7ZSaA95etk": "Lá Sen Cooking Class",
}
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯Ѐ-ӿ]")
NO_LISTING = re.compile(r"không có listing|không có cơ sở này|[Kk]hông xác nhận được")
NO_REVIEWS = re.compile(r"không có đánh giá")
# What the v1 Google Maps review wrote about hours. "Mở 24/24" (often Google's
# default) and partial hours still count as hours shown on Google Maps: our
# safe window is a subset of them. "Không có giờ" is missing information.
HOURS_SHOWN = re.compile(r"Giờ khớp Google|khớp dữ liệu|mở 24/24|mở cả ngày|chưa đầy đủ|"
                         r"đóng cửa \d|Google \d{1,2}:\d{2}")
HOURS_MISSING = re.compile(r"Google không (có|ghi) giờ")
DUP_M, DUP_RATIO = 50, 0.85          # same as structural test 2


def name_problem(name: str) -> str | None:
    """Why `name` is not a clean display name (gate G5), else None."""
    if "|" in name:
        return "có ký tự |"
    if CJK.search(name):
        return "có chữ Hàn/Trung/Nhật/Nga"
    if len(name) > 60:
        return "dài hơn 60 ký tự"
    return None


def clean_display_name(name: str) -> str:
    """Generic fallback for a name with no hand-checked fix: first `|` part,
    no CJK/Cyrillic words, no address/marketing tail after a dash or comma."""
    s = next((x.strip() for x in name.split("|") if x.strip()), name)
    s = " ".join(w for w in s.split() if not CJK.search(w))
    s = re.sub(r"\(\s*\)", "", s)
    if len(s) > 60:
        for sep in (" – ", " - ", ", ", ","):
            head = s.split(sep)[0].strip()
            if len(head) >= 6:
                s = head
                break
    s = re.sub(r"\s+", " ", s).strip(" -–,;:")
    return s[:60].rstrip() if len(s) > 60 else s


def google_evidence(rec, quarantine, gcheck, notes):
    """What Google Maps says about one POI, or None when it was never looked up.

    -> {listed, reviews, hours, closed, via}. Sources: the live check of
    19/11 (`google_maps_check_*.json`) for OSM POIs; the v1 crawl and the v1
    Google Maps review (quarantined) for the 750 v1 POIs."""
    pid = rec["poi_id"]
    g = gcheck.get(pid)
    if g:
        found = g.get("found", True)
        return {"listed": found, "reviews": g.get("review_count") if found else None,
                "hours": bool(g.get("hours_listed")), "closed": g.get("closed"),
                "via": "google_maps_check"}
    if pid not in notes and pid not in quarantine:
        return None
    q = quarantine.get(pid) or {}
    note = notes.get(pid) or ""
    reviews = q.get("review_count")
    if NO_REVIEWS.search(note):
        reviews = 0
    hours = bool(q.get("opening_hours")) or (
        bool(HOURS_SHOWN.search(note)) and not HOURS_MISSING.search(note))
    return {"listed": not NO_LISTING.search(note), "reviews": reviews,
            "hours": hours, "closed": None, "via": "google_v1"}


def _user_kept(rec) -> bool:
    return rec["provenance"]["status"]["source"] == "user_decision" and rec["status"] == "active"


def stop_reason(rec, ev, hours_conflict):
    """Drop rule for an active stop, or None to keep it."""
    sig = rec["popularity"]["signature"]
    if ev and ev["closed"]:
        return "closed", REASONS["closed_" + ev["closed"]] if "closed_" + ev["closed"] in REASONS \
            else REASONS["closed"]
    if sig:
        return None
    # A search miss on a site of the official old-town / Bà Nà ticket list is
    # a naming problem (Google lists many under an English name), not absence.
    if ev and not ev["listed"] and not (rec["requires_ticket_of"] and rec["role"] == "attraction"):
        return "not_listed", REASONS["not_listed"]
    if ev and ev["reviews"] is not None and ev["reviews"] < MIN_REVIEWS:
        return "few_reviews", REASONS["few_reviews"]
    if ev and ev["reviews"] is None and rec["popularity"]["audience"] == "local":
        return "few_reviews", REASONS["few_reviews_local"]
    inside_gate = bool(rec["requires_ticket_of"]) or rec["cluster_id"] == "ba_na"
    if rec["category"] in COMMERCIAL and rec["hours"]["kind"] != "fixed" and not inside_gate:
        if ev is None:
            return "no_hours", REASONS["no_hours_osm"]
        if not ev["hours"]:
            return "no_hours", REASONS["no_hours"]
    if rec["hours"]["kind"] == "unknown":
        return "no_hours", REASONS["no_hours"]
    if rec["poi_id"] in hours_conflict:
        return "hours_conflict", REASONS["hours_conflict"]
    return None


def _dup_key(name):
    return R.fold(name)


def find_duplicates(kept, ev_of, gcheck):
    """Pairs of kept stops that are one place: < 50 m apart and names >= 85 %
    alike (by own name, or by the Google name an OSM POI matched). The POI
    with more Google reviews stays; ties keep the v1 (Google id) record."""
    out = []
    for i, a in enumerate(kept):
        for b in kept[i + 1:]:
            if abs(a["lat"] - b["lat"]) > 0.0006 or abs(a["lon"] - b["lon"]) > 0.0006:
                continue
            if R.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) >= DUP_M:
                continue
            na = {_dup_key(a["name"]), _dup_key((gcheck.get(a["poi_id"]) or {}).get("gmaps_name") or a["name"])}
            nb = {_dup_key(b["name"]), _dup_key((gcheck.get(b["poi_id"]) or {}).get("gmaps_name") or b["name"])}
            if max(difflib.SequenceMatcher(None, x, y).ratio() for x in na for y in nb) < DUP_RATIO:
                continue

            def score(p):
                ev = ev_of.get(p["poi_id"]) or {}
                return (ev.get("reviews") or 0, p["poi_id"].startswith("ChIJ"), p["poi_id"])
            keep, drop = (a, b) if score(a) >= score(b) else (b, a)
            out.append((drop, keep))
    return out


def curate(recs, quarantine, gcheck, notes, hours_conflict, prov):
    """-> (kept records, dropped rows, summary). `prov` is migrate_v2.prov."""
    kept, dropped, ev_of = [], [], {}
    names_fixed, review_decided = [], []

    def drop(rec, rule, reason, by):
        dropped.append({"poi_id": rec["poi_id"], "name": rec["name"], "category": rec["category"],
                        "zone": rec["zone"], "rule": rule, "reason": reason, "decided_by": by})

    for rec in recs:
        by_status = rec["provenance"]["status"]["source"]
        if rec["status"] == "excluded":
            drop(rec, "excluded", rec["status_reason"], by_status)
            continue
        if rec["role"] == "base":
            drop(rec, "lodging", REASONS["lodging"], "auto_v23")
            continue
        if rec["status"] == "review":
            reason = REVIEW_DECISIONS.get(rec["poi_id"]) or rec["status_reason"] or "chưa phân loại được"
            review_decided.append(rec["poi_id"])
            drop(rec, "review", reason, "auto_v23")
            continue
        ev = google_evidence(rec, quarantine, gcheck, notes)
        ev_of[rec["poi_id"]] = ev
        why = None if _user_kept(rec) else stop_reason(rec, ev, hours_conflict)
        if why:
            drop(rec, why[0], why[1], f"auto_v23:{ev['via'] if ev else 'osm'}")
            continue
        kept.append(rec)

    for d, k in find_duplicates(kept, ev_of, gcheck):
        if _user_kept(d):
            continue
        kept.remove(d)
        drop(d, "duplicate", REASONS["duplicate"].format(k["name"]), "auto_v23")

    for rec in kept:
        if not name_problem(rec["name"]):
            continue
        new = NAME_FIXES.get(rec["poi_id"]) or clean_display_name(rec["name"])
        if new and new != rec["name"]:
            names_fixed.append({"poi_id": rec["poi_id"], "from": rec["name"], "to": new})
            rec["name"] = new
            rec["provenance"]["name"] = prov(
                "auto_name_v23", "inferred", confidence=0.6,
                note="tên hiển thị làm sạch tự động (bỏ chữ Hàn/Trung, phần quảng cáo); tên gốc ở name_raw")

    dropped.sort(key=lambda d: (RULES.index(d["rule"]), d["poi_id"]))
    summary = {"names_fixed": names_fixed, "review_decided": review_decided,
               "evidence_via": _count(ev["via"] if ev else "none" for ev in
                                      (ev_of.get(r["poi_id"]) for r in kept))}
    return kept, dropped, summary


def _count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))
