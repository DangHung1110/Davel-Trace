# Matrix calibration vs VietMap (motorcycle)

- Matrix: `BE/data/snapshots/danang-v1/matrix.json` (motorbike, OSM 2026-10-28T21:21:02Z, profile sha256 `925a1b2431d1`)
- Reference: VietMap Route v4 `vehicle=motorcycle`, run 2026-10-29
- Pairs: 49/50 answered, seed 20261029, stratified by matrix km
- Target: time MAPE <= 20% -> **FAIL**

| Time (minutes) | n | MAPE | median APE | p90 APE | bias |
|---|---|---|---|---|---|
| all (matrix minutes) | 49 | 22.3% | 23.7% | 32.0% | -17.8% |
| 0.5-2.0 km | 10 | 18.2% | 19.0% | 26.6% | +1.4% |
| 2.0-5.0 km | 10 | 16.3% | 16.6% | 22.8% | -13.9% |
| 5.0-10.0 km | 9 | 24.5% | 25.4% | 28.1% | -24.5% |
| 10.0-20.0 km | 10 | 24.0% | 23.7% | 29.6% | -24.0% |
| 20.0-+ km | 10 | 28.8% | 30.5% | 35.4% | -28.8% |
| all (exact OSRM seconds) | 49 | 21.5% | 22.5% | 30.3% | -16.9% |
| 0.5-2.0 km exact | 10 | 15.5% | 18.3% | 22.9% | +4.1% |
| 2.0-5.0 km exact | 10 | 15.7% | 13.9% | 24.2% | -12.7% |
| 5.0-10.0 km exact | 9 | 24.1% | 25.0% | 27.7% | -24.1% |
| 10.0-20.0 km exact | 10 | 23.7% | 23.7% | 28.4% | -23.7% |
| 20.0-+ km exact | 10 | 28.9% | 30.4% | 35.4% | -28.9% |

| Distance (km) | n | MAPE | median APE | p90 APE | bias |
|---|---|---|---|---|---|
| all | 49 | 4.0% | 1.7% | 8.8% | +1.0% |

SPEED_SCALE suggestion: multiply by **0.797** (fitted on 25 pairs). Holdout time MAPE 21.5% now, 13.0% projected (projected: scales durations only; rebuild and rerun to confirm).

1 pair(s) failed: Connection between locations not found
