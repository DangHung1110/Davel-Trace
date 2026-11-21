# PATM Model Card — trained on pairs v5 (2026-11-01)

Pairwise Attraction Transition Model: LightGBM pairwise classifier with 21
ordered-pair features. It predicts whether `first_id` should precede
`second_id` under the encoded transition preferences; it is not an end-to-end
itinerary generator.

## Training data

- Snapshot: `BE/data/snapshots/danang-v1`, 750 POIs, 716 of them in the pairs.
- Versioned pair file: `BE/ml/patm/pairs_v5_final.json`, 1,770 records.
- Source rows: 944 rule, 676 LLM-judge, 150 human. The human subset contains
  150 distinct unordered comparisons (51 prefer first, 57 prefer second,
  42 tie); it is 50 short of the original 200-human-pair target.
- 1,342 rows are used for training after dropping 428 ties. Rule and LLM
  labels are weak supervision; they are not human gold labels.

### What changed from v4

`pairs_v4_final.json` (2,028 records) is in git history before this card. The LLM judge was
asked both orders of 466 pairs and contradicted itself on 129 of them (28%):
125 named a different place to go first depending on the order of the question,
4 answered a tie one way and a preference the other. v5 drops those 258 rows
(`make_pairs.py --drop-contradictions`).
A pair asked in one order only cannot be checked and stays.

## Metrics

Latest full-data training (`train.py`, seed 7, 1.3 s on an M4 Pro):

| | v4 pairs | v5 pairs |
|---|---|---|
| 5-fold pair-group CV accuracy | 0.774 | **0.817** |
| Pair-group held-out accuracy | 0.749 (n=335) | **0.821** (n=252) |
| Flip consistency | 0.851 | **0.968** |

These group splits prevent mirrored pair leakage but do not prevent the same
POI from appearing in both train and held-out pairs. The rise in CV and
held-out accuracy partly reflects removing the rows hardest to predict, so it
does not show that the model got closer to people. Pair metrics against weak
labels are not user-satisfaction or itinerary-quality metrics.

### Against people, on places never seen

Human decisive pairs only, POIs held out of training (`evaluate.py`):

| | Correct | Accuracy |
|---|---|---|
| v5 model, 40 random splits | 1,129 / 1,603 | **70.4%** |
| v4 model, 40 random splits | 1,099 / 1,564 | 70.3% |
| Hand-written rule (`rule_score.py`), v5 splits | | 50.8% |

v5 beats v4 on 20 splits and loses on the other 20, so cleaning did not change
accuracy against people. About 70% against 50% is the figure to quote. The rule
counts a tie as wrong, and `rule_score.py` is the labelling rule rather than the
runtime fallback in `scorer.py`, which applies the same kinds of term.
`lpo_metrics.json` holds one split (28/38 model, 20/38 rule): with so few pairs
a single split moves by several points either way, and earlier figures of
81–83% came from a lucky split.

### What cleaning did change

On 6,320 ordered pairs of the 80 best known `main` POIs, the model gives one
clear direction to 93.0% of pairs (84.5% on v4), and the mean score falls from
+0.078 to +0.004. The v4 model leaned towards "yes" whatever the pair.

## How the planner uses it

- `scorer.edge_scores` gives the solver a score for every ordered pair of
  candidates. It helps choose WHICH stops enter a plan.
- The spread of scores on those 80 POIs (p10 to p90) is worth about 2.6 minutes
  of driving in the objective, so travel and stop value dominate.
- `route_order.best_order` then sets the final order by shortest travel and
  ignores this score. The model does not decide the order of the final plan.

See `docs/plan-accuracy.md` for plans measured with the model and with the rule.

## Known limits

- Human comparison coverage is limited to 150 distinct pairs; a blind
  evaluation split is smaller still. Collect more human judgments before
  treating the score as a stable estimate.
- Ties are dropped during binary model training; the model has no explicit
  tie prediction.
- **macOS needs libomp** (`brew install libomp`) for lightgbm to load. When the
  model cannot load, `scorer.py` silently uses its fallback rule and plans
  change: `scorer.describe()` says which backend answered.
- `train.py` passes no user or trip context, so the model never splits on 10 of
  its 21 features: the 4 `u_*`, the 4 `c_*`, `x_same_type` and `x_rain_cover`.
  It gives the same score to every traveller and to any weather. `d_rating` and
  `d_intensity` carry 71% of the gain.
- A POI with no training pair still gets a score from its features; nothing
  marks that score as less reliable.
- These results validate transition ordering only. Feasibility, route quality,
  weather correctness, and end-to-end itinerary quality use separate gates.

## Artifacts

- Model: `BE/ml/patm/model.txt`; metrics: `BE/ml/patm/model_metrics.json`,
  `BE/ml/patm/lpo_metrics.json`.
- Training pairs: `BE/ml/patm/pairs_v5_final.json`.
- Pair construction/evaluation tools: `make_pairs.py`, `train.py`,
  `evaluate.py`.
