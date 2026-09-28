# M2 dwell duration prior (T064, lane A) — NO TICK (gold pending)

Source: Foursquare-TKY consecutive same-venue gaps (raw in TEMP).
Method fixes applied honestly during build:
- 12h cap → absurd posteriors (landmark 520', transport 545' — revisits,
  not visits) → cap 4h + transport excluded (commute) + cap-pinned
  categories abstain to nac-1.
- `đ` NFD trap (same as T003c-N1FILL).

## Posteriors (n=1,136 dwells)

attraction 119 (high) / restaurant 38 (high) / market 16 (high) /
museum 58, cafe 62, nature 72, landmark 61 (medium) / park 85 (low) /
beach + transport: n=0 → nac-1 fallback.

Known bias: same-venue double-checkins select short lingerers —
posteriors run BELOW nac-1 defaults (smoke log-MAE 0.546 on seed 7).
Whether that is truer than defaults is exactly what gold decides.

## Pending real eval (user checklist)

Coverage ≥80% + MAE ≥10% better vs nac-1 on gold durations.
Phase-PR wiring: optimizer `get_p50()`, validator `get_p75()`
(`duration_prior.py` hooks; nac-1 fallback inside).
