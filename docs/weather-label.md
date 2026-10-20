# M4 weather labeler (T063, lane A) — NO TICK (audit pending)

> Confidence in this module is a **heuristic rule strength**, not a calibrated
> probability and not an accuracy claim. The real eval (macro-F1 >= 0.95 on
> human I/O/B labels) is still **PENDING** the manual audit. No GBDT is trained
> or required by the current classifier.

## OSM data (TEMP only, never committed)

Overpass (`fetch_osm.py`, node-only — 504 forced nwr→nodes + mirror
fallback): **Đà Nẵng 2,978** + Hội An 1,396 elements (tags only).
Known gaps: museums/parks are usually ways (node fetch misses them);
`has_building_polygon`/`area_m2` = 0/False until ways fetch for
shortlisted POIs lands.

**A node-only cache is not geometry.** A node point cannot prove polygon
containment or enclosure. To use R1/R2 geometry evidence the caller must supply
an OSM way/relation with polygon vertices, or an explicit
`name_linked`/`point_in_polygon` wrapper. Mere proximity is never inferred.

## v1 legacy rules (`featurize` / `label` / `label_element`)

Kept API-compatible for the existing smoke tests and wiring:
deterministic tag rules → indoor/outdoor + HEURISTIC confidence
(0.9 tag / 0.7 name-keyword / 0.5 default). Smoke on DN nodes:
indoor 2,655 / outdoor 323 (cafe/restaurant-heavy, expected).
The legacy `train_gbdt()` hook remains but is **not called** by the new
classifier; importing this module does not require LightGBM.

## v2 snapshot-POI classifier (`classify_poi`)

Pure, deterministic, dependency-free. It does not mutate the input.

```python
classify_poi(poi, audit=None, osm=None)
# aliases: classify_snapshot_poi; audit=human_label/audit_label;
#          osm=osm_evidence
```

### Inputs

- `poi`: snapshot POI dict (`name`, optional `lat`/`lon`, `cat`, `type`,
  `tags`, optional `io_label`).
- `audit`: optional human `I`/`O`/`B` (also accepts `indoor`/`outdoor`/`both`,
  or a dict with `label`/`space`/`io_label`/`io`). If omitted,
  `poi["io_label"]` is used as the snapshot audit field.
- `osm`: optional matched OSM element, wrapper
  `{"element": ..., "name_linked": true, "point_in_polygon": true}`, or a list.
  Polygon vertices may be Overpass-style `{"lat","lon"}` or GeoJSON-style
  `[lon, lat]`. If omitted, a POI's nested `osm_evidence` is used only when it
  actually contains an element/tags/geometry payload (not the snapshot's
  distance-only stub).

A supplied named element that neither name-matches the POI nor contains its
point is ignored as a nearby/unlinked feature. An anonymous polygon that does
not contain the POI is also ignored.

### Output schema

| Field | Values / meaning |
|---|---|
| `space` | `indoor` \| `outdoor` \| `both` \| `unknown` |
| `space_source` | `audit` \| `osm` \| `name` \| `canonical` |
| `space_confidence` | heuristic tier (see below), **uncalibrated** |
| `space_evidence` | list of human-readable evidence strings |
| `space_conflict` | list of preserved conflicts (never silently overwritten) |
| `rain_protection` | `enclosed` (R1) \| `sheltered` (R2) \| `none` \| `unknown` |
| `rain_protection_source` | `osm` \| `unknown` (rain is OSM-evidence only) |
| `rain_protection_confidence` | heuristic tier, **uncalibrated** |
| `rain_protection_evidence` | evidence strings, including ignored sun-only tags |
| `weather_sensitive` | derived bool (conservative; see below) |
| `confidence_kind` | always `heuristic_uncalibrated` |

### Precedence

1. **Human I/O/B audit wins for `space`** (`confidence = 1.0`). Any OSM/name
   disagreement is preserved in `space_conflict` as metadata; the audit is
   never overridden. The audit does **not** assert rain protection.
2. **OSM direct tags / name-linked or point-in-polygon way evidence.**
3. **Type/name keywords** (space only).
4. **Canonical snapshot default** (`confidence = 0.4`, explicitly heuristic;
   space only).

There is **no blanket default-indoor**. Ambiguous `attraction` / `market` /
`landmark` categories remain `unknown` unless OSM or name evidence is clearer.

### Rain protection (OSM evidence only)

`rain_protection` is **never** derived from the human audit, name keywords or
canonical category. Those decide `space` only. R1/R2/`none` require **linked OSM
evidence**; otherwise the result is `unknown` (abstention is not proof that
there is no cover).

### OSM Wiki rules

- **R1 `enclosed`**: explicit `indoor=yes` / `indoor=room` /
  `location=indoor` / `enclosed=yes`, or an actual linked/containing building polygon
  (`building=*` except `roof`/`no`).
- **R2 `sheltered`**: `building=roof`, `covered=yes`,
  `weather_protection=roof|awning|canopy`, a qualifying `amenity=shelter` /
  `weather_shelter`, and explicit `roof`/`awning`/`canopy`/`shelter` tags.
  R2 is **not** enclosed on its own and does **not** create `space=both`.
  `building=roof` also suppresses bare indoor-category inference; explicit
  `indoor=yes` / `location=indoor` / an actual enclosed building polygon still
  outrank it as R1.
- **Geometry is required for building polygons.** A `building=*` element with
  `type=way` but no polygon vertices is **not** polygon evidence (an OSM way
  may reference unfetched nodes). Actual vertices/containment, or explicit
  `name_linked`/`point_in_polygon` metadata from a caller that resolved the
  polygon, are required.
- **Sun-only is not rain protection**: `shade`, trees, parasols,
  `shelter_type=sun_shelter`, sun shelter/pergola/umbrella and similar
  tags/names are ignored for rain — even when `amenity=shelter` is also
  present without an explicit cover tag.
- **Clear open features may be `none`** (beach, park, playground, viewpoint,
  memorial, …). **Absent evidence is `unknown`**, not proof that there is no
  cover.
- `both` requires human audit `B` or explicit indoor+outdoor evidence
  (e.g. `indoor=yes` + `outdoor=yes`, or `outdoor_seating=yes` inside an
  enumerated indoor category/building). A partial roof never produces `both`.

### Weather sensitivity

- Audited `I` → `False`; audited `O` or `B` → `True` (existing semantics).
- `weather_sensitive` is derived from `space` only; `rain_protection` does not
  affect it, and an audited indoor POI still gets `rain_protection=unknown`
  unless linked OSM cover evidence exists.
- Non-audited: `outdoor`, `both`, `unknown`, or `space_confidence < 0.5`
  → `True`; confident `indoor` → `False`.
- Consequence: canonical indoor at `0.4` is still weather-sensitive. This is
  intentional and conservative.

### Confidence tiers (heuristic, not calibrated)

| Tier | Meaning |
|---|---|
| `1.0` | human audit |
| `0.8` | OSM tag/geometry + agreeing name evidence |
| `0.7` | unambiguous OSM tag/geometry |
| `0.6` | name keyword only |
| `0.4` | canonical default / abstention (unknown) |
| `0.3` | preserved conflict (audit conflicts keep `1.0`) |

When a non-audit space conflict is preserved, rain confidence is capped at
`0.3` too. Audit labels keep `1.0` and conflicts remain metadata.
These numbers encode rule strength only. They must not be reported as
probabilities or used as a calibrated accuracy claim.

## Wiring (phase-PR, STUB-note)

`weather_evidence()` strings → lane-B validator weather gate (T018 ext)
+ lane-C explainer (T042). `classify_poi` is ready for later snapshot wiring;
this step deliberately does **not** edit `enrich_snapshot.py`, snapshots,
HTML or any other files.

## Pending real eval (user I/O audit)

Macro-F1 ≥ 0.95 on audited indoor/outdoor labels. NO accuracy claim until then.
The 46 existing audited POI labels must be preserved when snapshot wiring lands;
their audit values are returned with confidence `1.0` and any conflict kept as
metadata. Rain-protection R1/R2 labels have no human ground truth yet.
