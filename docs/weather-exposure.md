# Weather exposure attributes (T063b)

Replaces the dead low-variance weather labels with continuous exposure
attributes and wires them into the PATM transition features. Numbers below are
from the `danang-v1` snapshot (764 POIs) and `C:\tmp\pairs_v4.json` (2151 pairs,
1697 trainable, 454 ties dropped).

## Why

Before this change, `smart_tags` carried:

| field | distribution (764 POIs) | problem |
|---|---|---|
| `space` | indoor 553 / unknown 120 / outdoor 86 / both 5 | 72% one class; entropy low |
| `rain_protection` | unknown 764 | entropy 0, no signal |

`BE/ml/patm/features.py` ignored `smart_tags` entirely (`_outdoor()` used a
3-type rule), so neither field could influence the transition model.

## Schema

New `smart_tags` fields (old `space` / `rain_protection` kept for backward
compatibility):

| field | type | values |
|---|---|---|
| `outdoor_exposure` | float 0..1 | 0 = sheltered/enclosed, 1 = fully exposed |
| `sun_exposure` | float 0..1 | 0 = no sun, 1 = full sun |
| `wind_exposure` | float 0..1 | 0 = wind-protected, 1 = fully wind-exposed |
| `rain_cover` | enum | enclosed \| covered \| mixed \| open \| unknown |

Floats are coarse rule **anchors**, not calibrated measurements. `unknown`
numeric evidence maps to the neutral `0.5` (a float cannot encode absence);
`rain_cover` keeps an explicit `unknown`.

### Precedence

`human audit > OSM evidence > canonical type default > unknown`

- Audit `I/O/B` maps to `indoor` (0.05/0/0, enclosed), `both`
  (0.5/0.4/0.4, mixed), `outdoor` (0.95/0.9/0.95, open).
- Linked OSM `space` evidence maps indoor/both/outdoor; linked OSM rain
  evidence (`enclosed`/`sheltered`/`none`) sharpens `rain_cover` to
  enclosed/covered/open.
- Mixed-use categories (`attraction`, `landmark`, `market`) stay intermediate
  (`rain_cover=mixed`, `outdoor_exposure` 0.55–0.65); they are never forced
  indoor.
- `rain_cover` in {enclosed, covered} caps sun/wind exposure (a roof blocks
  both).
- `rain_protection` keeps its old evidence-only semantics (audit alone does not
  assert rain). `rain_cover` is a separate coarse exposure proxy.

## Distribution after apply

Emitted by `BE/ml/data/enrich_snapshot.py --apply` to
`EXPOSURE_DISTRIBUTION.json` / `.md`:

| field | distinct | entropy (bits) | notable buckets |
|---|---|---|---|
| `outdoor_exposure` | 11 | 3.0461 | 0.05:129, 0.2:156, 0.55:90, 0.6:90, 0.65:49, 0.9:16, 0.95:18 |
| `sun_exposure` | 10 | 1.8374 | 0.05:445, 0.55:180, 0.8:16, 0.95:13 |
| `wind_exposure` | 9 | 2.3349 | 0.1:338, 0.45:140, 0.75:16, 0.95:18 |
| `rain_cover` | 3 | 1.1943 | enclosed:481, mixed:235, open:48 |

No new field collapses to a single value. `covered` / `unknown` rain_cover do
not occur on this snapshot because linked OSM evidence currently yields no
rain-shelter tags; those buckets are exercised by unit tests.

## QA follow-up fixes (T063b-2)

An independent 40-POI audit (`%TEMP%\t063_qa.md`) scored the committed `space`
labels at **28/40 (70.0%) strict**. The labeler now fixes:

1. **Diacritic false positives.** Matching is token-based on the
   accent-preserving Vietnamese name, with `_ACCENT_GUARD` for ambiguous
   single syllables: `Đào` (address) no longer hits `đảo` (island), `Cậu` no
   longer hits `cầu` (bridge), `sống` (fresh) no longer hits `sông` (river).
   A venue keyword now beats a descriptive outdoor word in business names, so
   `Coffee ... Lý Đạo Thành`, `Cà phê Cậu Út` and `Seavitel Beach Hotel` stay
   indoor instead of abstaining.
2. **OSM path now fires.** `--osm-cache` joins a raw Overpass export by
   exact folded-name match only (never proximity). The Da Nang cache
   (`C:\tmp\osm\danang.json`, kept in TEMP per `fetch_osm.py`) links 18 POIs;
   15 get `space_source=osm` (previously 0/764).
3. **Compound names.** Pagodas/churches → `both` (courtyard + hall), beer
   gardens → `both`, market halls (`chợ`) → `both`.
4. **Decisive landmark/beach names.** `bãi tắm`, `memorial`, `đài tưởng niệm`,
   `tượng đài` resolve to `outdoor` instead of the old ambiguous-canonical
   abstention.

Re-scoring the same QA sample against the new labels: **40/40 strict (100%)**,
up from 28/40. This is a small-sample diagnostic, not a calibrated accuracy
claim.

Snapshot `space` distribution before → after the follow-up:

| space | before | after |
|---|---|---|
| indoor | 553 (72.4%) | 501 (65.6%) |
| both | 5 (0.7%) | 105 (13.7%) |
| outdoor | 86 (11.3%) | 91 (11.9%) |
| unknown | 120 (15.7%) | 67 (8.8%) |

`space_source`: name 467, canonical 236, audit 46, **osm 15** (was 0).

## PATM features

| | before | after |
|---|---|---|
| feature count | 17 | 21 |
| appended | — | `x_outdoor_exposure`, `x_rain_cover`, `x_sun_exposure`, `x_wind_exposure` |

- Existing 17 features keep their order.
- `_outdoor()` now reads `smart_tags.outdoor_exposure` and falls back to the
  old type rule; the new features fall back to the canonical-type preset when a
  POI is not enriched yet.
- `x_rain_cover` maps enclosed 0.0 / mixed 0.5 / covered 0.7 / open 1.0 /
  unknown 0.5.
- All four new `x_*` features are antisymmetric diffs, preserving the
  ordered-pair flip contract (`extract(b,a) == -extract(a,b)` for these
  indices).
- The scorer's width guard is dynamic, so a 17-wide model falls back to the
  rule path until the model is retrained (it did, and the two transition tests
  failed loudly until the retrain below).

### Model metrics

| run | features | cv_acc | held_acc | flip |
|---|---|---|---|---|
| committed model (before) | 17 | 0.793 | 0.777 | 0.728 |
| re-run old extractor, same pairs (fair baseline) | 17 | 0.787 | 0.777 | 0.739 |
| after first retrain (pre-QA labels) | 21 | 0.782 | 0.777 | 0.736 |
| **after QA label fixes + retrain** | **21** | **0.785** | **0.786** | **0.730** |

Honest reading: the QA label fixes buy **+0.009 held-out accuracy** over both
17-feature baselines, while 5-fold CV is 0.002 below the fair baseline and flip
consistency is 0.009 below it (above the committed model by 0.002). This is a
mixed, small-sample result — no improvement claim beyond held-out accuracy.

## Reproduction

```powershell
$env:PYTHONPATH='.'
python BE/ml/data/enrich_snapshot.py --snapshot BE/data/snapshots/danang-v1 `
    --osm-cache C:\tmp\osm\danang.json --apply
python BE/ml/patm/train.py --pairs C:\tmp\pairs_v4.json `
    --snapshot BE/data/snapshots/danang-v1 --model-out BE/ml/patm/model.txt
python -m unittest discover -s BE/tests -t BE
```

## Risks / limitations

- Floats are rule anchors; they are not measured irradiance/wind and are not
  calibrated against human labels.
- OSM evidence is joined only on exact folded-name matches: 18 linked, 15
  sourced. Proximity-only matches are deliberately rejected, so 151 nearby
  elements stay unused; rain cover is still type-default driven in practice.
- The QA re-score is n=40; the 100% figure has a wide confidence interval and
  is not a population accuracy estimate.
- Coverage is uneven: 445/764 POIs sit at `sun_exposure=0.05` (indoor preset),
  so entropy is modest even though the field no longer collapses.
- The retrain overwrote `BE/ml/patm/model.txt` and `model_metrics.json`; the
  original 17-feature model remains recoverable from git at `932a0e1`.
