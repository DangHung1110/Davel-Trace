# T063 weather relabel report

- Tool version: `t063b-weather-exposure-v1`
- Generated (UTC): 2026-10-21
- POIs: 764
- Audit labels applied: 46
- Audit labels preserved exactly: 46
- Changed space labels: 73
- Changed rain-protection labels: 0
- Unique POIs with a changed weather label: 73
- Review rows: 200

## Space transitions (old -> new)

- `both->both`: 100
- `both->outdoor`: 5
- `indoor->both`: 6
- `indoor->indoor`: 490
- `indoor->outdoor`: 5
- `outdoor->both`: 1
- `outdoor->outdoor`: 90
- `unknown->both`: 14
- `unknown->indoor`: 11
- `unknown->outdoor`: 31
- `unknown->unknown`: 11

### Space sources

| key | count |
|---|---|
| audit | 46 |
| canonical | 172 |
| name | 531 |
| osm | 15 |

### Space confidence

| key | count |
|---|---|
| 0.4 | 172 |
| 0.6 | 531 |
| 0.7 | 7 |
| 0.8 | 8 |
| 1.0 | 46 |

### Rain protection

| key | count |
|---|---|
| unknown | 764 |

### Rain transitions (old -> new)

| key | count |
|---|---|
| unknown->unknown | 764 |

## Changed POIs

- `ChIJ00Fz0rANQjERLadxvkIRXBY` Thuyền Thúng Tượng Thúy - Coconut Basket Boat Tour Hoi An: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) thuyen, tuong
- `ChIJ08DIzjY9QjER4ldy4JXZBLA` Nhà Vọng Cảnh: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) nha vong canh
- `ChIJ17GORdEXQjERhkujx-kwJA0` Khu Du lịch Sinh thái Suối Rạng: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) suoi, sinh thai
- `ChIJ26h5ZAANQjER2otGJosJliA` Rường House - Cooking Class & Craft Workshop: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJ2y5L4dQNQjERxeSLc68fbrw` Ngũ Hành Sơn: unknown -> outdoor (canonical, conf 0.4) — canonical type/tags (thang canh) -> outdoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ5xkIv7EZQjERDZQIupNo09w` Bến Du Thuyền Đà Nẵng: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) du thuyen, thuyen, ben
- `ChIJ864pbQA9QjER--PIUcxqd48` Son Tra Viewpoint: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) viewpoint
- `ChIJ8ar-PNQXQjERFGGdrbCAQbg` Tháp Xá Lợi: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) thap
- `ChIJBQHuNG49QjER7Mb_Y2I64mk` Đỉnh Bàn Cờ: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) ban co
- `ChIJC0W3bjoYQjERVBMskQcoQck` Di tích Thành Điện Hải: unknown -> both (name, conf 0.6) — name compound keyword(s) di tich -> both
- `ChIJFbFDWA8ZQjERwNPaFGXBRPQ` F29 Golden Beef & Sky Bar: indoor -> both (name, conf 0.6) — name rooftop/terrace keyword(s) sky bar -> both
- `ChIJH1ujCM0XQjERcOl1lB9Ns6k` Tuyet Pham Cooking Class: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJI4oSjdE9QjERlXMiA630YKs` Hải đăng Tiên Sa: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) hai dang
- `ChIJK4sVPc0ZQjERdGROWQ8MMg4` Trung Tâm Giải Trí Helio: unknown -> both (canonical, conf 0.4) — canonical type/tags (trung tam vui choi) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJKytgDsgQQjER6al50BDd7vc` Hòn Thủy Sơn: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) hon
- `ChIJLTomluP3QTERUy-b9iAYR8U` Khu du lịch sinh thái Suối Hoa: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) suoi, sinh thai
- `ChIJNdWwUgARQjERansIEJQleAU` Động Tàng Chơn: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) dong
- `ChIJO0IiWR0RQjERtGkQtqESJ1Y` Động Vân Thông: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) dong
- `ChIJO5_PAj8XQjER34kyBjbMYNo` Family Kitchen Da Nang - Cooking Class: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJOxVypBYRQjERMmK2P6JbzF0` Động Âm Phủ: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) dong
- `ChIJQWQVKr4ZQjERcafNnRyLelk` DD WONDERLAND: unknown -> indoor (canonical, conf 0.4) — canonical type/tags (trong nha) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJSRWy6Hr3QTERiU3vuI0PbHw` Khu Du Lịch Sinh Thái Lái Thiêu: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) sinh thai
- `ChIJT1zm9U8NQjERQf5DsBriCgc` Dịch Vụ Thuyền Thúng Bến Dừa: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) thuyen, ben
- `ChIJT9jHPuANQjERQTnqjbIQIF8` Thuyền thúng Dũng Thúy: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) thuyen
- `ChIJVVmn6uMjQjERwv0F2ZV9pJw` Bãi Sủng Cỏ: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) bai
- `ChIJZ6w1fJgZQjERP9-_TlpgQXM` Lagoon Rooftop - Dragon Bridge Fire Show: outdoor -> both (name, conf 0.6) — name rooftop/terrace keyword(s) rooftop -> both
- `ChIJZQZGM-MZQjERm_6vbq_fWzo` NYX Sky Lounge & Mixology: indoor -> both (name, conf 0.6) — name rooftop/terrace keyword(s) sky lounge -> both
- `ChIJZWmMe1g9QjERrOGO9nVdagQ` Khu nghỉ mát Du lịch sinh thái Tiên Sa: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) sinh thai
- `ChIJ_XkaoQs-QjER_IUTHqI3gI8` Mũi Nghê: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) mui
- `ChIJaa7lANcXQjERmT3kgV5U7uA` Bảo tàng Đồng Đình: indoor -> both (name, conf 0.6) — name compound keyword(s) dinh -> both
- `ChIJabEOcucXQjER-8MNU9FNODw` Tượng Quan Thế Âm Bồ Tát: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) tuong
- `ChIJabHpMJoXQjERgyUE4Jz8_D0` BlackOut Rooftop Bar: indoor -> both (name, conf 0.6) — name rooftop/terrace keyword(s) rooftop -> both
- `ChIJddXz2K8PQjER4enhapQvvo8` Cooking With Jolie In Hoi An – Vietnamese Cooking Class: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJg2m14V0ZQjERt4DjGOdJDiE` Jolie Cooking Class: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJg5OvAgAhQjERKbrq9-Wza-U` Khu Du Lịch Sinh Thái Thuỷ Vân Sơn: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) sinh thai
- `ChIJgaVvkV0XQjERNZYSVEJS_Xo` Marine Sky Bar-Rooftop SeaView with Exclusive Spa Offers: indoor -> both (name, conf 0.6) — name rooftop/terrace keyword(s) rooftop, sky bar -> both
- `ChIJiXlEK7IRQjERvpdL4vcW86w` Tượng Phật Đá Phan Sơn: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) tuong
- `ChIJkatEeMwZQjERnAUKgmrbNgQ` Làng Bích họa Đà Nẵng: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) lang
- `ChIJo8N_zUw9QjERgutJ9u3-n7Y` View Ngắm Bình Minh Sơn Trà: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) binh minh, view ngam
- `ChIJp9cNzfwZQjERS7ZSaA95etk` Danang Cooking Class - Lá Sen ダナン料理教室: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJpYNhNwAXQjERflfHrn1lop4` Vịnh Sơn Trà: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) vinh
- `ChIJq56yCur3QTERYlOCLaSCVwQ` Làng Toom Sara Đà Nẵng: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) lang
- `ChIJq7Uto10fQjERQgZQB_w3cBw` Cổng Chào Khu Công Nghệ Cao Đà Nẵng: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) cong chao
- `ChIJqXp39lv2QTERR9U4pFNMD2o` Mercure Danang French Village Bana Hills: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) village
- `ChIJrQINf-wZQjEREXiFm4Gq56M` Da Nang Family Cooking Class: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJs-NDcgAXQjERHA6tioqOfH4` Apron Up Cooking Class in Danang: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJs5puLQA9QjERIaHbrBAGpjA` Dịch Vụ Cano Du Lịch Lặn Biển Ngắm San Hô Sơn Trà: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) cano, lan bien, ngam san ho, san ho
- `ChIJsztPMVkXQjERooynSorot-0` Blue Sky Bar: indoor -> both (name, conf 0.6) — name rooftop/terrace keyword(s) sky bar -> both
- `ChIJx0dBXWYNQjERQzQO18QYhas` Mimi Cooking Class: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) cooking class
- `ChIJyWFmArX3QTERon6tUT6re4Q` Ba Na Hills: unknown -> outdoor (canonical, conf 0.4) — canonical type/tags (thang canh) -> outdoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJyZOJHa8NQjERSvp9yMenV6Y` Vinh Vo Cooking Class: unknown -> indoor (name, conf 0.6) — name venue keyword(s) cooking class beat descriptive outdoor keyword(s) vinh -> indoor
- `ChIJzUoWGdQXQjEReYmzPE0JBDw` Tượng Phật Nhập Niết Bàn: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) tuong
- `manual:hai-van-quan` Hải Vân Quan: unknown -> both (canonical, conf 0.4) — canonical type/tags (di tich) -> both (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/10709724107` Làng đá mỹ nghệ Non Nước: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) lang
- `osm:node/10709738005` Làng chiếu Cẩm Nê: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) lang
- `osm:node/10709738105` Làng nước mắm Nam Ô: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) lang
- `osm:node/11832500969` Rào chắn: unknown -> outdoor (canonical, conf 0.4) — canonical type/tags (ngam canh) -> outdoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/12404434601` Khu Văn hóa Tâm linh Đà Sơn: unknown -> both (name, conf 0.6) — name compound keyword(s) tam linh -> both
- `osm:node/13008480396` Miếu xóm: unknown -> both (name, conf 0.6) — name compound keyword(s) mieu -> both
- `osm:node/1335374752` miếu Thần Nông: unknown -> both (name, conf 0.6) — name compound keyword(s) mieu -> both
- `osm:node/1335374818` miếu Ngài Ngư: unknown -> both (name, conf 0.6) — name compound keyword(s) mieu -> both
- `osm:node/1335374895` miếu Âm Hồn: unknown -> both (name, conf 0.6) — name compound keyword(s) mieu -> both
- `osm:node/13484040419` Đền Bà Càn Khôn: unknown -> both (canonical, conf 0.4) — canonical type/tags (co so tho tu) -> both (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/13687068650` Linh Phong Bảo Tháp: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) thap
- `osm:node/13734880501` Tượng Phật Phước Lý: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) tuong
- `osm:node/4005611262` Đền thờ Tiền Hiền làng Lổ Giang: unknown -> both (name, conf 0.6) — name compound keyword(s) den tho -> both
- `osm:node/4005611263` Đình Lổ Giáng: unknown -> both (name, conf 0.6) — name compound keyword(s) dinh -> both
- `osm:node/4924323121` Fishing Village and Fleet: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) village
- `osm:node/6332518185` Miếu Xóm An Mỹ: unknown -> both (name, conf 0.6) — name compound keyword(s) mieu -> both
- `osm:node/6346486685` Cây đa đại thụ: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) cay da
- `osm:node/6369465978` Vietnamese Mother Statue: unknown -> both (canonical, conf 0.4) — canonical type/tags (co so tho tu) -> both (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/6513792708` Đình Phục Đán: unknown -> both (name, conf 0.6) — name compound keyword(s) dinh -> both
- `osm:node/6528451001` Cây đa Đò Xu: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) cay da

## Conflict IDs

ChIJBcr6kegZQjER2nCllYpT_Qc, ChIJFad1TFAXQjERE9B6U1THHT4, ChIJM5BHkDAZQjERYlaJyu15KFg, ChIJO56jTAARQjEREYLpKFOB1DA, ChIJP1Uz6i0ZQjERfy-rpM1cGWc, ChIJqSwlvMkZQjERE_9aVr3pkes, ChIJrcJ8wVwRQjERJF58LAQEO-I, ChIJz0Od5IUXQjERmAV9JgLRqm8
