# M4 weather labeler (T063, lane A) — NO TICK (audit pending)

## OSM data (TEMP only, never committed)

Overpass (`fetch_osm.py`, node-only — 504 forced nwr→nodes + mirror
fallback): **Đà Nẵng 2,978** + Hội An 1,396 elements (tags only).
Known gaps: museums/parks are usually ways (node fetch misses them);
`has_building_polygon`/`area_m2` = 0/False until ways fetch for
shortlisted POIs lands.

## Labeler v1 (`labeler.py`)

Deterministic tag rules → indoor/outdoor + HEURISTIC confidence
(0.9 tag / 0.7 name-keyword / 0.5 default). Smoke on DN nodes:
indoor 2,655 / outdoor 323 (cafe/restaurant-heavy, expected).
`train_gbdt()` implemented, runs when audit labels exist.

## Wiring (phase-PR, STUB-note)

`weather_evidence()` strings → lane-B validator weather gate (T018 ext)
+ lane-C explainer (T042). No cross-lane edits from here.

## Pending real eval (user I/O audit)

Macro-F1 ≥ 0.95 on audited indoor/outdoor labels. NO accuracy claim
until then — confidence values are uncalibrated heuristics.
