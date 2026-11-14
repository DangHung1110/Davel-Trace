# Matrix calibration vs VietMap (motorcycle)

- Matrix: `BE/data/snapshots/danang-v1/matrix.json` (motorbike, OSM 2026-10-28T21:21:02Z, profile sha256 `1a920cd0a8ea`)
- Reference: VietMap Route v4 `vehicle=motorcycle`, run 2026-10-29
- Pairs: 49/50 answered, seed 20261029, stratified by matrix km
- Target: time MAPE <= 20% -> **PASS**

| Time (minutes) | n | MAPE | median APE | p90 APE | bias |
|---|---|---|---|---|---|
| all (matrix minutes) | 49 | 7.8% | 4.2% | 16.1% | +1.7% |
| 0.5-2.0 km | 10 | 11.9% | 11.8% | 16.3% | +3.2% |
| 2.0-5.0 km | 9 | 9.0% | 6.1% | 15.2% | +9.0% |
| 5.0-10.0 km | 10 | 4.7% | 3.5% | 10.3% | +2.7% |
| 10.0-20.0 km | 10 | 1.8% | 1.4% | 3.3% | -0.6% |
| 20.0-+ km | 10 | 11.7% | 4.4% | 34.3% | -5.1% |
| all (exact OSRM seconds) | 49 | 6.8% | 3.3% | 15.9% | +2.9% |
| 0.5-2.0 km exact | 10 | 10.3% | 9.3% | 19.7% | +10.2% |
| 2.0-5.0 km exact | 9 | 6.5% | 4.4% | 10.0% | +6.4% |
| 5.0-10.0 km exact | 10 | 4.2% | 3.0% | 10.0% | +3.5% |
| 10.0-20.0 km exact | 10 | 1.5% | 1.2% | 3.3% | -0.3% |
| 20.0-+ km exact | 10 | 11.6% | 4.7% | 33.8% | -4.8% |

| Distance (km) | n | MAPE | median APE | p90 APE | bias |
|---|---|---|---|---|---|
| all | 49 | 3.5% | 1.2% | 4.3% | -0.4% |

SPEED_SCALE suggestion: multiply by **1.009** (fitted on 25 pairs). Holdout time MAPE 9.2% now, 8.8% projected (projected: scales durations only; rebuild and rerun to confirm).

1 pair(s) failed: Connection between locations not found
