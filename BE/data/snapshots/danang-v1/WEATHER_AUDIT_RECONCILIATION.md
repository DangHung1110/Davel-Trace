# Weather label audit reconciliation

- Updated: 2026-10-26
- Snapshot: 745 POIs remain after 19 explicit removals.
- Review 200 export: 181 labeled, 19 blank. Every blank is now accounted for: 18 removals including Rào chắn, plus VỌC Glamping retained and labeled outdoor.
- QA seed 999 export: 38/40 answered; 7 overlap review and all seven agree.
- Independent completed QA responses: 27/31 (87.1%) agree with frozen pre-audit labels. The four differences were explicitly adjudicated by the reviewer below; this is not gold-standard accuracy.
- Combined unique decisions: 213; 212 labels retained in the current snapshot.

## Final adjudications

- SAY Beer — indoor
- Phố đi bộ - chợ đêm Bạch Đằng Đà Nẵng — outdoor
- Chợ Cồn — indoor
- Khu Ẩm Thực Chợ Cồn — indoor
- VỌC Glamping — outdoor
- Rào chắn — removed

## Other clean-up applied

- Removed the 18 previously listed POIs plus Rào chắn (19 removals total).
- Kept VỌC Glamping as an outdoor activity.
- Both Sơn Trà viewpoint POIs now use type/tag `Điểm ngắm cảnh` and `cat=viewpoint`.
- Removed street addresses from `Bê Thui Thiên 2` and `Bếp nhà Hà`.
- Renamed Chùa Tam Bảo to `Chùa Tam Bảo (Chùa Tam Bảo Theravāda)`.

## Final snapshot QA and API readiness

- Snapshot checks: 745 POIs, 745 unique IDs; 19 removals match the change from the optimizer's 764-POI snapshot. No POI IDs were added.
- `smart_tags.space`: 504 indoor, 128 outdoor, 109 both, 4 unknown. Unknown POIs have no numeric outdoor exposure.
- `smart_tags.rain_cover`: 504 enclosed, 109 mixed, 128 open, 4 unknown. `rain_protection` remains unknown for all 745 because no source proves actual shelter coverage; this is separate from the coarse `rain_cover` feature.
- Do not rerun enrichment with `--apply` unless the original OSM cache is supplied. A read-only run without that cache would change two existing labels and drop OSM provenance; the audited snapshot was kept unchanged.
- Matrix cache needs a rebuild against the final top-150-by-rating selection: 3 stale POIs were removed and 3 current POIs need route rows. The local OSRM service at `127.0.0.1:5000` is not running, so the missing route times were not fabricated.
- The historical `RELABEL_REPORT` records the earlier 764-POI enrichment run; use this section and `EXPOSURE_DISTRIBUTION` for final snapshot counts.
