# Kiểm chứng độc lập số liệu audit POI (CHỈ ĐỌC)

- Ngày: 2026-11-18 · Snapshot: `BE/data/snapshots/danang-v1/pois.json` (snapshot=danang-v1, source=serpapi/google-maps, fetched_at=2026-10-03, enriched_at=2026-10-26)
- Script: `reports/audit_scripts/crosscheck.py` (chỉ thư viện chuẩn, không gọi API ngoài, không đọc `data_audit_20261118.md`)
- Giả định: "có toạ độ" = không None/NaN/0 (toạ độ ngoài khung vẫn được tính là có, và rơi vào B). "Đóng cửa" khớp trên chuỗi đã lowercase; đ→d khi so trùng tên.

## 1. Tổng số POI
| Chỉ số | Giá trị | Trường / nguồn |
|---|---|---|
| Số POI thực tế | 742 | len(pois['pois']) |
| Metadata count | 745 | pois['count'] |
| Chênh lệch (thực − metadata) | -3 | — |
| poi_id duy nhất | 742 | poi_id |

## 2. Phân bố cat / type
Nhóm nhà hàng + cà phê (cat ∈ restaurant, cafe): **236** POI. Số cat khác nhau: 13; số type khác nhau: 102.

**cat** (trường `cat`):
| cat | Số POI |
|---|---|
| restaurant | 128 |
| cafe | 108 |
| attraction | 87 |
| landmark | 85 |
| spa | 77 |
| lodging | 76 |
| bar | 69 |
| market | 49 |
| beach | 16 |
| nature | 16 |
| museum | 15 |
| park | 14 |
| viewpoint | 2 |

**type** (trường `type`, top 20):
| type (top 20) | Số POI |
|---|---|
| Quán cà phê | 106 |
| Điểm thu hút khách du lịch | 62 |
| Khách sạn | 58 |
| Nhà hàng | 44 |
| Spa | 44 |
| Chùa phật giáo | 34 |
| Quán bar | 34 |
| Nhà hàng hải sản | 26 |
| Cơ sở thờ tự | 19 |
| Spa mát xa | 17 |
| Nhà hàng Việt Nam | 16 |
| Chợ | 16 |
| Khách sạn nghỉ dưỡng | 15 |
| Nhà thờ Công giáo | 14 |
| Lớp học nấu ăn | 14 |
| Quán bar karaoke | 13 |
| Cửa hàng quà lưu niệm | 12 |
| Quán mì | 12 |
| Đỉnh núi | 11 |
| Quán bar cocktail | 11 |

## 3. Nghi trùng (khoảng cách < 50 m và độ giống tên ≥ 0.85)
Trường: `name`, `lat`, `lon`. Độ giống: `difflib.SequenceMatcher` trên tên đã bỏ dấu.
Số cặp nghi trùng: **0** (số POI liên quan: **0**). Chẩn đoán: có **108** cặp < 50 m (bất kể tên), độ giống tên lớn nhất trong nhóm đó = **0.684**.

Không có cặp nào.

## 4. Toạ độ
| Trạng thái toạ độ (trường lat, lon) | Số POI |
|---|---|
| Thiếu (None/NaN/0) | 0 |
| Ngoài khung lon 107.2–108.8 / lat 14.9–16.3 | 0 |
| Nghi đảo lat/lon (đảo vào khung) | 0 |
| Hợp lệ (trong khung) | 742 |

Phân bố khoảng cách haversine tới Cầu Rồng (16.0612, 108.2275), trường lat/lon, chỉ POI có toạ độ:
| Khoảng cách tới Cầu Rồng (haversine) | Số POI |
|---|---|
| 0–5 km | 439 |
| 5–15 km | 254 |
| 15–40 km | 49 |
| >40 km | 0 |

## 5. opening_hours
| Kiểu dữ liệu opening_hours | Số POI |
|---|---|
| list | 742 |

| Nhóm (opening_hours) | Số POI |
|---|---|
| Rỗng ([] / null / "") | 243 |
| Parse được (HH:MM-HH:MM) | 483 |
| Parse được (24/7) | 0 |
| Không parse (có dữ liệu) | 16 |

Mẫu 10 POI không parse (trường `opening_hours`):
| poi_id | Trạng thái | Giá trị thô (cắt 80 ký tự) |
|---|---|---|
| ChIJHyNg3TIYQjERqz7x0udvRd0 | rong | [] |
| ChIJZSsvT9QZQjERf-oLnsT1C3Y | khong_parse | ['11:00-15:00, 17:00-22:30', '11:00-15:30, 17:00-23:00'] |
| ChIJ-VaWslgZQjERwaL3uKR9fB4 | khong_parse | ['10:30-14:00, 17:00-02:00'] |
| ChIJYahwiHIXQjER0CIGd09pgcg | khong_parse | ['10:00-14:00, 16:00-22:00'] |
| ChIJ4UuIQXgXQjERz192UgYuxMU | khong_parse | ['11:00-14:00, 17:00-22:00'] |
| ChIJYQkmfagfQjER0iIRsKZ0Rcc | rong | [] |
| ChIJ1eef2IsZQjERjy-_tblqzJs | khong_parse | ['10:00-14:00, 16:00-20:30'] |
| ChIJ1yFjaOwZQjERO43leJW7YHk | khong_parse | ['10:00-14:00, 16:00-21:00'] |
| ChIJ0RbSL4ARQjERLwRYqY1bqp4 | rong | [] |
| ChIJvb3YtJYXQjERnLJ4-sFfc6A | rong | [] |

Tổng không parse = 16; trong đó **16** POI có chuỗi nhiều khoảng giờ ("HH:MM-HH:MM, HH:MM-HH:MM"), regex một khoảng không khớp.

## 6. Giá
| Trường | Phân bố / số có | Số POI |
|---|---|---|
| price_level | 1:103, 2:579, 3:60 | 742 |
| fee | 0:742 | 742 |
| ticket_vnd (khác null) | — | 13 |
| price_note (khác rỗng) | — | 262 |

## 7. verified_at
| Chỉ số (trường verified_at) | Giá trị |
|---|---|
| Số có verified_at | 410 |
| Khoảng min – max | 2026-10-08 – 2026-10-29 |
| Trong 12 tháng (2025-11-18 → 2026-11-18) | 410 |
| Ngày tương lai (> 2026-11-18) | 0 |
| Không parse được ngày | 0 |

## 8. Phân hạng A / B / C theo cat
| cat | A | B | C | Tổng |
|---|---|---|---|---|
| restaurant | 106 | 22 | 0 | 128 |
| cafe | 90 | 18 | 0 | 108 |
| attraction | 30 | 57 | 0 | 87 |
| landmark | 20 | 65 | 0 | 85 |
| spa | 48 | 29 | 0 | 77 |
| lodging | 0 | 76 | 0 | 76 |
| bar | 46 | 23 | 0 | 69 |
| market | 25 | 24 | 0 | 49 |
| beach | 11 | 5 | 0 | 16 |
| nature | 2 | 14 | 0 | 16 |
| museum | 7 | 8 | 0 | 15 |
| park | 6 | 8 | 0 | 14 |
| viewpoint | 1 | 1 | 0 | 2 |
| **Tổng** | 392 | 350 | 0 | 742 |

Quy tắc ưu tiên: C (thiếu toạ độ/cat, nghi trùng, hoặc chữ đóng cửa) > A (toạ độ trong khung, giờ parse được, source có, verified_at trong 12 tháng) > B (phần còn lại). Chữ "đóng cửa|closed|ngừng hoạt động" (khớp chuỗi thuần) khớp **504** POI, nhưng toàn bộ đến từ `smart_tags.rain_cover` = "enclosed" (chứa "closed"). Dùng ranh giới từ `\bclosed\b`, số POI khớp là **0** → C do đóng cửa chỉ tính theo 0. Biến thể không dấu ("dong cua|ngung hoat dong") khớp 0 POI. B có toạ độ nghi đảo/ngoài khung: **0** (theo quy tắc, các POI này nằm ở B, không ở A). Nhóm lodging có A = 0: 76 / 76 POI lodging không có opening_hours, 76 không có verified_at.

## 9. Độ phủ (khác rỗng)
| Trường | Số POI khác rỗng | Tỷ lệ |
|---|---|---|
| ambience | 0 | 0.0% |
| pros | 0 | 0.0% |
| cons | 0 | 0.0% |
| visit_min | 742 | 100.0% |
| intensity | 742 | 100.0% |
| weather_sensitive | 742 | 100.0% |
| smart_tags.time | 665 | 89.6% |
| tags | 741 | 99.9% |
| osm_evidence | 223 | 30.1% |
| web_evidence | 63 | 8.5% |

```json
{
  "n_pois": 742,
  "meta_count": 745,
  "diff_count": -3,
  "unique_poi_id": 742,
  "resto_cafe_n": 236,
  "n_cat_distinct": 13,
  "n_type_distinct": 102,
  "dup_pairs": 0,
  "dup_pois": 0,
  "near_50m_pairs_any_name": 108,
  "near_50m_max_sim": 0.684,
  "coord_states": {
    "hop_le": 742
  },
  "bridge_buckets": {
    "0–5 km": 439,
    "5–15 km": 254,
    "15–40 km": 49,
    ">40 km": 0
  },
  "hours": {
    "types": {
      "list": 742
    },
    "empty": 243,
    "parsed": 483,
    "parsed_kinds": {
      "HH:MM-HH:MM": 483
    },
    "unparsed_nonempty": 16,
    "unparsed_multi_range": 16
  },
  "price": {
    "price_level": {
      "2": 579,
      "3": 60,
      "1": 103
    },
    "fee": {
      "0": 742
    },
    "ticket_vnd": 13,
    "price_note": 262
  },
  "verified": {
    "present": 410,
    "min": "2026-10-08",
    "max": "2026-10-29",
    "in_12m": 410,
    "future": 0,
    "unparsable": 0
  },
  "grades": {
    "A": 392,
    "B": 350
  },
  "closed_hits": 0,
  "closed_literal_hits": 504,
  "closed_noaccent_hits": 0,
  "cat_missing": 0,
  "B_with_invalid_coords": 0,
  "coverage": {
    "ambience": 0,
    "pros": 0,
    "cons": 0,
    "visit_min": 742,
    "intensity": 742,
    "weather_sensitive": 742,
    "smart_tags.time": 665,
    "tags": 741,
    "osm_evidence": 223,
    "web_evidence": 63
  }
}
```
