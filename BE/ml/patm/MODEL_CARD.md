# PATM Model Card — v4 (2026-10-17)

Pairwise Attraction Transition Model: LightGBM pairwise ranker, 17 features
(`BE/ml/patm/features.py`), predicts P(first POI before second | context).

## Training data (T028)

- Snapshot `BE/data/snapshots/danang-v1`, n=764 POIs, 752 covered by pairs.
- 2151 pairs: 1000 rule + 973 Qwen3-8B local-judge + 178 human-verify.
  (25 stale pairs referencing review-dropped POIs removed.)
- Balance prefer-first/tie/prefer-second = 45.6 / 21.3 / 33.0
  (LLM judges vote decisive more often than the 30/40/30 rule target).
- Swap-check on stored pairs: 0 inconsistent. Leave-POI-out split:
  train 1371 / eval 805, 0 leaked.

## Metrics (T029/T031)

- 5-fold CV accuracy: **0.793** (ties excluded from training rows)
- Held-out accuracy: **0.777** (n=345)
- Flip consistency (mirror-pair agreement): **0.728**
- Top features by gain: d_rating, d_intensity, x_meal_after, d_duration,
  x_indoor_buffer, prior_logp. Price/context/user-profile features ≈ 0
  (no user signal in lane A; context features activate in lane B wiring).

## Known limits

- Flip 0.728 < v3 0.902: LLM labels on 440 new POIs are noisier and ties
  are dropped at train time, so the model under-learns symmetry.
  Follow-up (lane B): keep ties at 0.5 sample weight + temperature
  calibration before optimizer wiring (T030).
- 12 POIs have no pairs (long tail); they fall back to rule_score.
- ticket=null on 21 POIs, hours missing on ~50: optimizer must treat as
  unconstrained, never as closed/free.

## Artifacts

- `model.txt` (this version), metrics in `model_metrics.json`
- pairs: `C:/tmp/pairs_v4.json` (rebuildable via make_pairs + judge batch)
