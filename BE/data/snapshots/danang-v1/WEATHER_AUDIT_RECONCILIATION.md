# Weather label audit reconciliation

- Updated: 2026-10-27
- Snapshot: 742 POIs remain after 22 explicit removals.
- Review 200 export: 181 labeled, 19 blank. Every blank is now accounted for: 18 removals including Rào chắn, plus VỌC Glamping retained and labeled outdoor.
- QA seed 999 export: 38/40 answered; 7 overlap review and all seven agree.
- Independent completed QA responses: 27/31 (87.1%) agree with frozen pre-audit labels. The four differences were explicitly adjudicated by the reviewer below; this is not gold-standard accuracy.
- Combined unique decisions: 215; 214 labels retained in the current snapshot, including the user-confirmed Nhất Lâm Thủy Trang Trà and Cầu Rồng decisions.

## Final adjudications

- SAY Beer — indoor
- Phố đi bộ - chợ đêm Bạch Đằng Đà Nẵng — outdoor
- Chợ Cồn — indoor
- Khu Ẩm Thực Chợ Cồn — indoor
- VỌC Glamping — outdoor
- Nhất Lâm Thủy Trang Trà — outdoor
- Cầu Rồng — outdoor (confirmed; existing standalone POI)
- Rào chắn — removed
- Queen Cobra — removed (Da Nang Downtown is closed)
- Dragon's Head — removed (not a Google Maps POI)
- Pont main — removed (not a Google Maps POI)

## Other clean-up applied

- Removed the 18 previously listed POIs plus Rào chắn, Queen Cobra, Dragon's Head, and Pont main (22 removals total).
- Kept VỌC Glamping as an outdoor activity.
- Both Sơn Trà viewpoint POIs now use type/tag `Điểm ngắm cảnh` and `cat=viewpoint`.
- Removed street addresses from `Bê Thui Thiên 2` and `Bếp nhà Hà`.
- Renamed Chùa Tam Bảo to `Chùa Tam Bảo (Chùa Tam Bảo Theravāda)`.

## Final snapshot QA and API readiness

- Snapshot checks: 742 POIs, 742 unique IDs; 22 removals from the optimizer's 764-POI snapshot. No POI IDs were added.
- `smart_tags.space`: 504 indoor, 129 outdoor, 109 both, 0 unknown. The previously unknown Nhất Lâm Thủy Trang Trà now has the user's outdoor audit label.
- `smart_tags.rain_cover`: 504 enclosed, 109 mixed, 129 open, 0 unknown. `rain_protection` remains unknown for all 742 because no source proves actual shelter coverage; this is separate from the coarse `rain_cover` feature.
- Snapshot enrichment was applied with the original `C:\tmp\osm\danang.json` cache: 18 OSM evidence links were retained. Do not rerun `--apply` without that cache; a check without it changes two existing labels and loses OSM provenance.
- Matrix rebuilt on 2026-10-27 against the final top-150-by-rating selection: 150 IDs, 22,500/22,500 cells from OSRM, no haversine seeds, no stale or missing IDs. Artifact: `matrix.json`; commit `65ecdbc`.
- All 742 POIs now have a resolved `space` label; Cầu Rồng remains its own outdoor POI (`ChIJL1GKWJYZQjERLrEGqlK2kwQ`).
- `rain_protection=unknown` for all 742 remains intentional: no linked evidence establishes actual shelter coverage. Keep it unknown until evidence is gathered; this does not block use of the separate coarse `rain_cover` field.
- `RELABEL_REPORT` and `EXPOSURE_DISTRIBUTION` were regenerated from the final 742-POI snapshot.
- PATM was retrained on the final snapshot using 2,028 valid pairs. The 123 source-pair rows touching removed POIs were excluded; 1,596 rows were trainable after dropping ties. Metrics: CV 0.770, held-out 0.773 (n=335), flip consistency 0.776. See `BE/ml/patm/model_metrics.json`; filtered pairs remain in local `C:\tmp\pairs_v4_final.json`.
