# Weather exposure attributes (T063b)

> **Current data status (2026-10-27):** the final `danang-v1` snapshot has 745
> POIs after manual review; `space` is indoor 504, outdoor 128, both 109,
> unknown 4. The top-150 route matrix is rebuilt with 22,500/22,500 OSRM
> cells. See
> [`WEATHER_AUDIT_RECONCILIATION.md`](../BE/data/snapshots/danang-v1/WEATHER_AUDIT_RECONCILIATION.md)
> and [`EXPOSURE_DISTRIBUTION.md`](../BE/data/snapshots/danang-v1/EXPOSURE_DISTRIBUTION.md)
> for the final snapshot. Historical counts and model metrics below describe
> earlier 764-POI runs and are retained as experiment history.

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

Floats are coarse rule **anchors**, not calibrated measurements. When the
space decision is `unknown`, snapshot floats are `null` and `rain_cover` is
`unknown`; PATM may use its category prior when it consumes a missing value.

### Precedence

One committed space decision (`human audit > linked OSM > name > canonical
type`) drives all four exposure fields. Unknown remains missing instead of
being changed into a neutral-looking exposure score.

- Audit `I/O/B` maps to `indoor` (0.05/0/0, enclosed), `both`
  (0.5/0.4/0.4, mixed), `outdoor` (0.95/0.9/0.95, open).
- Linked OSM `space` evidence maps indoor/both/outdoor; linked OSM rain
  evidence (`enclosed`/`sheltered`/`none`) sharpens `rain_cover` to
  enclosed/covered/open.
- Mixed-use categories (`attraction`, `landmark`, `market`) are resolved from
  type/name evidence when available; otherwise they remain unknown. Rooftop
  and sky-bar cues resolve to `both` with outdoor exposure, not an indoor bar
  category prior.
- An `outdoor` space can never have `rain_cover=enclosed`; `unknown` space has
  three missing exposure floats and `rain_cover=unknown`.
- `rain_cover` in {enclosed, covered} caps sun/wind exposure (a roof blocks
  both).
- `rain_protection` keeps its old evidence-only semantics (audit alone does not
  assert rain). `rain_cover` is a separate coarse exposure proxy.

## Distribution after apply

Emitted by `BE/ml/data/enrich_snapshot.py --apply` to
`EXPOSURE_DISTRIBUTION.json` / `.md`:

| field | distinct | entropy (bits) | notable buckets |
|---|---|---|---|
| `outdoor_exposure` | 11 | 2.2315 | 0.1:412, 0.6:110, 0.75:56, missing:11 |
| `sun_exposure` | 10 | 1.7890 | 0.05:501, 0.48:110, 0.75:56, missing:11 |
| `wind_exposure` | 11 | 2.2315 | 0.1:412, 0.48:110, 0.75:56, missing:11 |
| `rain_cover` | 4 | 1.3446 | enclosed:501, mixed:121, open:131, unknown:11 |

At this historical generation, the 764-POI snapshot had 501 indoor, 131
outdoor, 121 both, and 11 unknown POIs. The final audited snapshot counts are
listed at the top of this document and in `EXPOSURE_DISTRIBUTION.md`. Unknown
POIs retain missing exposure floats; no `outdoor`/`enclosed` contradictions
are allowed. No linked OSM rain-shelter tags were found; the `covered` case is
exercised by unit tests.

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

The reported 40/40 re-score used the same seed-42 examples that informed the
rules, so it is a tuning result and **not** a generalization estimate. A
separate blind seed-777 sample with no overlap scored 29/40 (72.5%) strict;
excluding seven borderline cases gives 90% under the broader rubric. Treat
72.5% as the strict result. The seed-42/seed-777 sample manifests are not in
this repo, so those two QA scores are recorded from the operator's report.

Snapshot `space` distribution before → after the follow-up:

| space | before | after |
|---|---|---|
| indoor | 553 (72.4%) | 501 (65.6%) |
| both | 5 (0.7%) | 121 (15.8%) |
| outdoor | 86 (11.3%) | 131 (17.1%) |
| unknown | 120 (15.7%) | 11 (1.4%) |

Final snapshot `space_source`: name 440, audit 248, canonical 42, OSM 15.
The current checks catch DD WONDERLAND as indoor and Marine Sky Bar as both;
exposure now follows those final space decisions. Four ambiguous POIs remain
unknown pending manual review; see the reconciliation report for their names.

The blind audit pages were regenerated after the system fixes. The 200-row review page is a priority sample for manual cleanup;
`weather_label_qa_seed999_blind.html` is a deterministic 40-POI sample from
the full snapshot. The exported audit contains 181/200 review labels and
38/40 QA labels. Seven QA POIs overlap the review sample, with all seven
answers agreeing. On the 31 answered non-overlap QA POIs, 27 (87.1%) agree
with the frozen pre-audit labels. This is agreement with the prior classifier,
not independently adjudicated ground-truth accuracy. The exports plus final adjudications contain 213 unique decisions; 212 labels
remain in the snapshot after one labeled POI was removed. The reviewer removed
19 POIs total, finalized the four QA disagreements, classified VỌC Glamping as
outdoor, and corrected three names and two viewpoint categories. See
`BE/data/snapshots/danang-v1/WEATHER_AUDIT_RECONCILIATION.md` for details.

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
| after space/exposure consistency fix + retrain | 21 | 0.786 | 0.765 | 0.765 |

The latest retrain improves flip consistency to 0.765, but held-out accuracy
is 0.012 below the fair 17-feature baseline. The model result does not show an
overall gain; the system fix addresses label consistency. Do not treat model
metrics as proof that the human-facing labels are accurate.

## Reproduction

```powershell
$env:PYTHONPATH='.'
python BE/ml/data/enrich_snapshot.py --snapshot BE/data/snapshots/danang-v1 `
    --osm-cache C:\tmp\osm\danang.json --apply
python BE/ml/patm/train.py --pairs C:\tmp\pairs_v4.json `
    --snapshot BE/data/snapshots/danang-v1 --model-out BE/ml/patm/model.txt
python -m unittest discover -s BE/tests -t BE
python -m BE.ml.weather_label.render_review --input `
    BE/data/snapshots/danang-v1/weather_review_200.json --blind
python -m BE.ml.weather_label.render_review --snapshot `
    BE/data/snapshots/danang-v1 --blind --seed 999 --limit 40
```

After choosing labels in the blind page, export JSON and pass it back to the
snapshot tool with `--audit-json <downloaded-file> --check`; use `--apply`
after reviewing the dry-run output. Choices are joined by stable `poi_id` and
override earlier labels for those reviewed POIs.

## Risks / limitations

- Floats are rule anchors; they are not measured irradiance/wind and are not
  calibrated against human labels.
- OSM evidence is joined only on exact folded-name matches: 18 linked, 15
  sourced. Proximity-only matches are deliberately rejected, so 151 nearby
  elements stay unused; rain cover is still type-default driven in practice.
- QA seed-999 has 31 answered non-overlap rows after excluding seven repeated
  POIs and two blanks. Its 27/31 agreement is a small-sample comparison with
  frozen predictions, not a gold-standard accuracy estimate.
- Coverage is uneven: 445/764 POIs sit at `sun_exposure=0.05` (indoor preset),
  so entropy is modest even though the field no longer collapses.
- The retrain overwrote `BE/ml/patm/model.txt` and `model_metrics.json`; the
  original 17-feature model remains recoverable from git at `932a0e1`.
