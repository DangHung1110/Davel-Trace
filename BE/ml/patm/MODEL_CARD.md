# PATM Model Card — v5 (2026-10-27)

Pairwise Attraction Transition Model: LightGBM pairwise classifier with 21
ordered-pair features. It predicts whether `first_id` should precede
`second_id` under the encoded transition preferences; it is not an end-to-end
itinerary generator.

## Training data

- Snapshot: `BE/data/snapshots/danang-v1`, 742 POIs.
- Versioned pair file: `BE/ml/patm/pairs_v4_final.json`, 2,028 records after
  removing 123 records that reference POIs removed from the final snapshot.
- Source rows: 944 rule, 934 LLM-judge, 150 human. The human subset contains
  150 distinct unordered comparisons (51 prefer first, 57 prefer second,
  42 tie); it is 50 short of the original 200-human-pair target.
- 1,596 rows are used for training after dropping 432 ties. Rule and LLM
  labels are weak supervision; they are not human gold labels.
- Rebuild pair format check: 0 errors; leave-POI-out split check reports
  train 1,302 / eval 726 with no POI leakage.

## Metrics

Latest full-data training (`train.py`, seed 7):

- 5-fold pair-group CV accuracy: **0.770**.
- Pair-group held-out accuracy: **0.773** (n=335).
- Flip consistency: **0.776**.

These group splits prevent mirrored pair leakage but do not prevent the same
POI from appearing in both train and held-out pairs. See the separate
leave-POI-out human evaluation in `lpo_metrics.json` before making a
generalization claim. Pair metrics against weak labels are not user-satisfaction
or itinerary-quality metrics.

## Known limits

- Human comparison coverage is limited to 150 distinct pairs; a blind
  evaluation split is smaller still. Collect more human judgments before
  treating the score as a stable estimate.
- Ties are dropped during binary model training; the model has no explicit
  tie prediction.
- Long-tail POIs without pair coverage fall back to `rule_score`.
- These results validate transition ordering only. Feasibility, route quality,
  weather correctness, and end-to-end itinerary quality use separate gates.

## Artifacts

- Model: `BE/ml/patm/model.txt`; metrics: `BE/ml/patm/model_metrics.json`.
- Training pairs: `BE/ml/patm/pairs_v4_final.json`.
- Pair construction/evaluation tools: `make_pairs.py`, `train.py`,
  `evaluate.py`.
