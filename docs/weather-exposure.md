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
| `outdoor_exposure` | 11 | 3.0292 | 0.05:129, 0.2:163, 0.55:91, 0.6:90, 0.65:49, 0.9:16, 0.95:18 |
| `sun_exposure` | 9 | 1.8257 | 0.05:445, 0.55:181, 0.8:16, 0.95:13 |
| `wind_exposure` | 9 | 2.3021 | 0.1:352, 0.45:140, 0.75:16, 0.95:18 |
| `rain_cover` | 3 | 1.1943 | enclosed:481, mixed:235, open:48 |

No new field collapses to a single value. `covered` / `unknown` rain_cover do
not occur on this snapshot because it currently has **no linked OSM
rain-protection evidence**; those buckets are exercised by unit tests and will
appear once OSM evidence is joined.

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
| **after retrain** | **21** | **0.782** | **0.777** | **0.736** |

Honest reading: **the new exposure features do not improve pairwise accuracy**
(cv −0.005 vs fair baseline, held flat) and flip consistency is slightly below
the fair re-run (−0.003) though above the committed model (+0.008). The
exposure attributes add signal diversity but the current pairs dataset does not
convert it into better ordering. No claim of improvement is made.

## Reproduction

```powershell
$env:PYTHONPATH='BE'
python BE/ml/data/enrich_snapshot.py --snapshot BE/data/snapshots/danang-v1 --apply
python BE/ml/patm/train.py --pairs C:\tmp\pairs_v4.json `
    --snapshot BE/data/snapshots/danang-v1 --model-out BE/ml/patm/model.txt
python -m unittest discover -s BE/tests -t BE
```

## Risks / limitations

- Floats are rule anchors; they are not measured irradiance/wind and are not
  calibrated against human labels.
- The snapshot has no linked OSM rain evidence yet, so `rain_cover` is driven
  by type defaults in practice and `covered`/`unknown` are unobserved.
- Coverage is uneven: 445/764 POIs sit at `sun_exposure=0.05` (indoor preset),
  so entropy is modest even though the field no longer collapses.
- The retrain overwrote `BE/ml/patm/model.txt` and `model_metrics.json`; the
  17-feature model remains recoverable from git history at `932a0e1`.
