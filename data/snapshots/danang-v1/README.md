# Snapshot danang-v1 (seed T003)

Seed 7 POIs distinct từ FE `DemoTripData`
(`origin/feat/flutter-mobile-shell:FE/lib/features/itinerary/domain/demo_trip.dart`):
3 origins (`dragon-bridge`, `danang-airport`, `han-market`) + 4 activities
(`son-tra`, `mi-quang-ba-mua`, `cham-museum`, `my-khe`).

## Files

- `pois.json` — 7 POIs theo schema TravelEval (`data-model.md` POI).
  `visit_min` do `BE/ml/patm/estimate_duration.py` nấc-1 sinh
  (`dur_source=category_rule`, `dur_confidence=low`).
  Verify: `python BE/ml/patm/estimate_duration.py --check data/snapshots/danang-v1/pois.json`
- `matrix.json` — 7×7 seed tạm (haversine 30km/h, min 5 phút, `source=cache`).
  Ma trận OSRM thật thay ở T010. Không dùng làm chứng cứ khả thi ngoài demo.
- Full snapshot 100–200 POIs (T003b) sẽ thay file này sau human spot-check 15%.

## Nguồn

`source = "FE DemoTripData (seed T003)"`, `verified = true` cho cả 7
(đủ điều kiện vào lịch chính demo US1).
