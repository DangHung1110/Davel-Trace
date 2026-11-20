"""Fetch OPEN data for danang-v2 (run on a machine with normal internet).

    python BE/ml/data/fetch_open_data.py osm          # OSM match + gap candidates
    python BE/ml/data/fetch_open_data.py popularity   # Wikidata + Wikipedia pageviews
    python BE/ml/data/fetch_open_data.py all
    python BE/ml/data/migrate_v2.py                   # rebuild v2 with the results

Sources and terms (all allowed by TRAVELAGENT_CONTEXT.md rule 5):
- Overpass API (OSM, ODbL - attribution "© OpenStreetMap contributors").
- Wikidata SPARQL (CC0) and Wikimedia pageviews REST API.
Requests are cached under BE/data/sources/cache/ and rate-limited; a
descriptive User-Agent is sent as Wikimedia requires.

Outputs (never edit pois.json directly; migrate_v2.py consumes them):
- BE/data/sources/osm_match.json     {poi_id: {osm, dist_m, name_ratio, tags}}
- BE/data/sources/osm_gap_candidates.json  new-POI CANDIDATES for zones that
  lack meal/rest (hoi_an, ba_na_tay). They are NOT added automatically: a human
  picks <= GIOI_HAN_POI_MOI (150) of them; adding them is a separate, reviewed
  step (new POIs also need matrix rows).
- BE/data/sources/popularity.json    {poi_id: {wikidata, wikidata_sitelinks,
  wikipedia_views_90d}}
Stdlib only.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v2_rules as R  # noqa: E402

# Wikimedia requires a User-Agent with real contact info (URL or e-mail) and
# answers 429 otherwise. The contact is set by the person running the fetch:
#   $env:WIKIMEDIA_UA = "Davel-TravelAgent/0.2 (<your contact>)"
UA = os.environ.get("WIKIMEDIA_UA",
                    "Davel-TravelAgent/0.2 (student research project; contact: repo owner)")
SRC = os.path.join("BE", "data", "sources")
CACHE = os.path.join(SRC, "cache")
SNAP = os.path.join("BE", "data", "snapshots", "danang-v2", "pois.json")
OVERPASS = "https://overpass-api.de/api/interpreter"
WD_SPARQL = "https://query.wikidata.org/sparql"
PAGEVIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
             "{project}/all-access/user/{title}/daily/{start}/{end}")
BBOX = (15.70, 107.80, 16.25, 108.60)        # s, w, n, e - Đà Nẵng + Hội An area
GAP_ZONES = {"hoi_an": (15.84, 108.28, 15.93, 108.42),
             "ba_na_tay": (15.95, 107.95, 16.08, 108.12)}


def _get(url, data=None, pause=1.0, accept="application/json"):
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1((url + (data or "")).encode()).hexdigest()
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, data=data.encode() if data else None,
                                 headers={"User-Agent": UA, "Accept": accept})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read().decode("utf-8"))
            break
        except Exception as e:  # noqa: BLE001 - network errors vary
            if attempt == 2:
                raise
            print("retry", url[:80], e)
            time.sleep(5 * (attempt + 1))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    time.sleep(pause)
    return out


def _pois():
    with open(SNAP, encoding="utf-8") as f:
        return json.load(f)["pois"]


def _dump(name, obj):
    os.makedirs(SRC, exist_ok=True)
    with open(os.path.join(SRC, name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote", os.path.join(SRC, name))


# --------------------------------------------------------------------------
# OSM
# --------------------------------------------------------------------------

OSM_QUERY = """[out:json][timeout:240];
(
  nwr["name"]["amenity"]({s},{w},{n},{e});
  nwr["name"]["tourism"]({s},{w},{n},{e});
  nwr["name"]["shop"]({s},{w},{n},{e});
  nwr["name"]["leisure"]({s},{w},{n},{e});
  nwr["historic"]({s},{w},{n},{e});
  nwr["natural"~"beach|peak|waterfall|water|bay|cape"]["name"]({s},{w},{n},{e});
);
out center tags;"""
# 20/11: widened from attractions/food only to every named amenity/tourism/
# shop/leisure element — hotels, spas, massage, karaoke, clubs and shops were
# missing, so 627 Google-origin POIs could only reach 17% OSM links.


def fetch_osm():
    s, w, n, e = BBOX
    data = _get(OVERPASS, data="data=" + urllib.parse.quote(OSM_QUERY.format(s=s, w=w, n=n, e=e)),
                pause=2.0)
    els = []
    for el in data.get("elements", []):
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        tags = el.get("tags") or {}
        if lat is None or not tags.get("name"):
            continue
        els.append({"osm": f"{el['type']}/{el['id']}", "lat": lat, "lon": lon, "tags": tags})
    print("osm elements", len(els))

    pois = _pois()
    match = {}
    for p in pois:
        best = None
        for el in els:
            if abs(el["lat"] - p["lat"]) > 0.0015 or abs(el["lon"] - p["lon"]) > 0.0015:
                continue
            d = R.haversine_m(p["lat"], p["lon"], el["lat"], el["lon"])
            names = [el["tags"].get(k, "") for k in ("name", "name:vi", "name:en")]
            ratio = max(difflib.SequenceMatcher(None, R.fold(p["name"]), R.fold(nm)).ratio()
                        for nm in names if nm) if any(names) else 0
            # same rule as migrate_v2.osm_name_ok: one name containing the other
            # ("Mộc quán Seafood Đà Nẵng" / "Mộc Quán") is a match
            a = R.fold(p["name"])
            if a and any(nm and (R.fold(nm) in a or a in R.fold(nm)) for nm in names):
                ratio = max(ratio, 0.9)
            score = ratio - d / 300.0
            if d <= 120 and ratio >= 0.6 and (best is None or score > best["score"]):
                best = {"osm": el["osm"], "dist_m": round(d, 1), "name_ratio": round(ratio, 2),
                        "score": score, "tags": {k: v for k, v in el["tags"].items()
                                                 if k in ("name", "name:en", "name:vi", "opening_hours",
                                                          "fee", "charge", "wikidata", "wikipedia",
                                                          "tourism", "amenity", "historic", "cuisine")}}
        if best:
            best.pop("score")
            match[p["poi_id"]] = best
    _dump("osm_match.json", {"source": "OpenStreetMap via Overpass (ODbL)",
                             "fetched_at": time.strftime("%Y-%m-%d"), "items": match})

    known = {m["osm"] for m in match.values()} | {p["ext_ids"]["osm"] for p in pois if p["ext_ids"]["osm"]}
    cands = []
    for zone, (s2, w2, n2, e2) in GAP_ZONES.items():
        for el in els:
            if el["osm"] in known or not (s2 <= el["lat"] <= n2 and w2 <= el["lon"] <= e2):
                continue
            t = el["tags"]
            role = ("meal" if t.get("amenity") in ("restaurant", "fast_food", "marketplace") else
                    "rest" if t.get("amenity") in ("cafe",) else
                    "nightlife" if t.get("amenity") in ("bar", "pub") else "attraction")
            cands.append({"zone": zone, "role_guess": role, "osm": el["osm"], "lat": el["lat"],
                          "lon": el["lon"], "name": t.get("name"), "name_en": t.get("name:en"),
                          "opening_hours": t.get("opening_hours"), "fee": t.get("fee"),
                          "wikidata": t.get("wikidata"),
                          "category_guess": R.classify(t.get("name", ""), None, None)[0]})
    _dump("osm_gap_candidates.json", {"note": "CHƯA thêm vào snapshot. Người dùng chọn <= 150.",
                                      "items": cands})


# --------------------------------------------------------------------------
# popularity
# --------------------------------------------------------------------------

def fetch_popularity():
    """Wikidata items near each attraction-role POI -> sitelinks + 90-day views."""
    pois = [p for p in _pois() if p["role"] == "attraction" and p["status"] != "excluded"]
    q = """SELECT ?item ?itemLabel ?coord ?sitelinks ?viwiki ?enwiki WHERE {
      SERVICE wikibase:box { ?item wdt:P625 ?coord .
        bd:serviceParam wikibase:cornerSouthWest "Point(%f %f)"^^geo:wktLiteral .
        bd:serviceParam wikibase:cornerNorthEast "Point(%f %f)"^^geo:wktLiteral . }
      ?item wikibase:sitelinks ?sitelinks .
      OPTIONAL { ?viwiki schema:about ?item ; schema:isPartOf <https://vi.wikipedia.org/> . }
      OPTIONAL { ?enwiki schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "vi,en". }
    }""" % (BBOX[1], BBOX[0], BBOX[3], BBOX[2])
    data = _get(WD_SPARQL + "?format=json&query=" + urllib.parse.quote(q),
                accept="application/sparql-results+json", pause=2.0)
    items = []
    for b in data["results"]["bindings"]:
        lon, lat = b["coord"]["value"].replace("Point(", "").replace(")", "").split()
        items.append({"qid": b["item"]["value"].rsplit("/", 1)[-1], "label": b["itemLabel"]["value"],
                      "lat": float(lat), "lon": float(lon), "sitelinks": int(b["sitelinks"]["value"]),
                      "viwiki": b.get("viwiki", {}).get("value"), "enwiki": b.get("enwiki", {}).get("value")})
    print("wikidata items", len(items))
    end = time.strftime("%Y%m%d")
    start = time.strftime("%Y%m%d", time.gmtime(time.time() - 90 * 86400))
    out = {}
    for p in pois:
        best = None
        for it in items:
            d = R.haversine_m(p["lat"], p["lon"], it["lat"], it["lon"])
            if d > 800:
                continue
            ratio = difflib.SequenceMatcher(None, R.fold(p["name"]), R.fold(it["label"])).ratio()
            if ratio >= 0.6 and (best is None or ratio - d / 2000 > best[0]):
                best = (ratio - d / 2000, it, d, ratio)
        if not best:
            continue
        _, it, d, ratio = best
        views = 0
        for url, project in ((it["viwiki"], "vi.wikipedia"), (it["enwiki"], "en.wikipedia")):
            if not url:
                continue
            title = urllib.parse.quote(urllib.parse.unquote(url.rsplit("/", 1)[-1]), safe="")
            try:
                pv = _get(PAGEVIEWS.format(project=project, title=title, start=start, end=end), pause=0.2)
                views += sum(x["views"] for x in pv.get("items", []))
            except Exception as e:  # noqa: BLE001
                print("pageviews miss", title, e)
        out[p["poi_id"]] = {"wikidata": it["qid"], "wikidata_label": it["label"],
                            "match_m": round(d, 1), "name_ratio": round(ratio, 2),
                            "wikidata_sitelinks": it["sitelinks"], "wikipedia_views_90d": views}
    _dump("popularity.json", out)


WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"


def _views_90d(project, title):
    end = time.strftime("%Y%m%d")
    start = time.strftime("%Y%m%d", time.gmtime(time.time() - 90 * 86400))
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    try:
        pv = _get(PAGEVIEWS.format(project=project, title=t, start=start, end=end), pause=0.2)
        return sum(x["views"] for x in pv.get("items", []))
    except Exception as e:  # noqa: BLE001 - a missing article counts as 0
        print("pageviews miss", title, e)
        return 0


def fetch_popularity_api():
    """Fallback when the Wikidata SPARQL service (WDQS) is down/rate-limited.

    Wikipedia geosearch around each attraction POI (vi + en), name match
    (fold ratio >= 0.6, <= 800 m), then `pageprops.wikibase_item` -> Wikidata
    `wbgetentities` sitelink count, plus 90-day pageviews. Same output schema
    as `fetch_popularity`.
    """
    pois = [p for p in _pois() if p["role"] == "attraction" and p["status"] != "excluded"]
    out = {}
    for p in pois:
        best = None
        for lang in ("vi", "en"):
            q = {"action": "query", "list": "geosearch", "gscoord": f"{p['lat']}|{p['lon']}",
                 "gsradius": 800, "gslimit": 20, "format": "json"}
            res = _get(WIKI_API.format(lang=lang) + "?" + urllib.parse.urlencode(q), pause=0.3)
            for g in res.get("query", {}).get("geosearch", []):
                ratio = difflib.SequenceMatcher(None, R.fold(p["name"]), R.fold(g["title"])).ratio()
                f_name, f_title = R.fold(p["name"]), R.fold(g["title"])
                if f_title and (f_title in f_name or f_name in f_title):
                    ratio = max(ratio, 0.8)
                score = ratio - g["dist"] / 2000
                if ratio >= 0.6 and (best is None or score > best[0]):
                    best = (score, lang, g, ratio)
        if not best:
            continue
        _, lang, g, ratio = best
        props = _get(WIKI_API.format(lang=lang) + "?" + urllib.parse.urlencode(
            {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
             "pageids": g["pageid"], "format": "json"}), pause=0.3)
        page = next(iter(props.get("query", {}).get("pages", {}).values()), {})
        qid = (page.get("pageprops") or {}).get("wikibase_item")
        sitelinks, views = None, 0
        if qid:
            ent = _get(WD_API + "?" + urllib.parse.urlencode(
                {"action": "wbgetentities", "ids": qid, "props": "sitelinks", "format": "json"}),
                pause=0.3)
            links = (ent.get("entities", {}).get(qid) or {}).get("sitelinks") or {}
            sitelinks = len(links)
            for wiki, project in (("viwiki", "vi.wikipedia"), ("enwiki", "en.wikipedia")):
                if wiki in links:
                    views += _views_90d(project, links[wiki]["title"])
        else:
            views = _views_90d(f"{lang}.wikipedia", g["title"])
        out[p["poi_id"]] = {"wikidata": qid, "wikidata_label": g["title"],
                            "match_m": round(g["dist"], 1), "name_ratio": round(ratio, 2),
                            "wikidata_sitelinks": sitelinks, "wikipedia_views_90d": views,
                            "via": f"{lang}.wikipedia geosearch"}
    print("popularity matches", len(out), "of", len(pois))
    _dump("popularity.json", out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["osm", "popularity", "popularity-api", "all"])
    a = ap.parse_args(argv)
    if a.what in ("osm", "all"):
        fetch_osm()
    if a.what in ("popularity", "all"):
        try:
            fetch_popularity()
        except Exception as e:  # noqa: BLE001 - WDQS outage / 429
            print("WDQS unavailable, using Wikipedia/Wikidata APIs instead:", e)
            fetch_popularity_api()
    if a.what == "popularity-api":
        fetch_popularity_api()


if __name__ == "__main__":
    main()
