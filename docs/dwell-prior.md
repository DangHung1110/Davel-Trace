# M2 dwell duration prior (T064, lane A) — NO TICK (gold pending)

Source: Foursquare-TKY consecutive same-venue gaps (raw in TEMP).
Method fixes applied honestly during build:
- 12h cap → absurd posteriors (landmark 520', transport 545' — revisits,
  not visits) → cap 4h + transport excluded (commute) + cap-pinned
  categories abstain to nac-1.
- `đ` NFD trap (same as T003c-N1FILL).

## Posteriors (regenerated DIRECTLY from duration_prior.json, 2026-09-28)

| category | n | confidence | p25 | p50 | p75 |
|---|---|---|---|---|---|
| attraction | 235 | high | 52.6 | 119.0 | 174.4 |
| beach | 0 | low | 84.0 | 120.0 | 168.0 |
| cafe | 69 | medium | 24.7 | 62.5 | 158.9 |
| landmark | 44 | medium | 26.5 | 60.7 | 113.9 |
| market | 453 | high | 9.0 | 16.2 | 59.0 |
| museum | 38 | medium | 29.8 | 58.2 | 115.8 |
| nature | 59 | medium | 37.9 | 72.5 | 161.2 |
| park | 15 | low | 58.2 | 84.8 | 139.7 |
| restaurant | 223 | high | 17.2 | 37.9 | 89.2 |
| transport | 0 | low | 14.0 | 20.0 | 28.0 |
| TOTAL | **1136** | | | | |

beach + transport n=0 → nac-1 fallback.

Known bias: same-venue double-checkins select short lingerers —
posteriors run BELOW nac-1 defaults (smoke log-MAE 0.546 on seed 7).
Whether that is truer than defaults is exactly what gold decides.

## Pending real eval (user checklist)

Coverage ≥80% + MAE ≥10% better vs nac-1 on gold durations.
Phase-PR wiring: optimizer `get_p50()`, validator `get_p75()`
(`duration_prior.py` hooks; nac-1 fallback inside).
