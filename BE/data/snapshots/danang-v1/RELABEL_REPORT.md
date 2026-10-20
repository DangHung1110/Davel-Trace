# T063 weather relabel report

- Tool version: `t063-weather-wiring-v1`
- Generated (UTC): 2026-10-20
- POIs: 764
- Audit labels applied: 46
- Audit labels preserved exactly: 46
- Changed space labels: 261
- Changed rain-protection labels: 551
- Unique POIs with a changed weather label: 717
- Review rows: 200

## Space transitions (old -> new)

- `both->both`: 5
- `both->indoor`: 102
- `both->outdoor`: 30
- `both->unknown`: 96
- `indoor->indoor`: 450
- `indoor->outdoor`: 8
- `indoor->unknown`: 21
- `outdoor->indoor`: 1
- `outdoor->outdoor`: 48
- `outdoor->unknown`: 3

### Space sources

| key | count |
|---|---|
| audit | 46 |
| canonical | 275 |
| name | 443 |

### Space confidence

| key | count |
|---|---|
| 0.3 | 21 |
| 0.4 | 275 |
| 0.6 | 422 |
| 1.0 | 46 |

### Rain protection

| key | count |
|---|---|
| unknown | 764 |

### Rain transitions (old -> new)

| key | count |
|---|---|
| rain-proof->unknown | 551 |
| unknown->unknown | 213 |

## Changed POIs

- `ChIJ-cf9B7wQQjERutUzeynzw8w` Chùa Quán Thế Âm: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJ0-6wNdsXQjER068QxYa3E5o` Karaoke Song Ca: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJ00Fz0rANQjERLadxvkIRXBY` Thuyền Thúng Tượng Thúy - Coconut Basket Boat Tour Hoi An: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ08DIzjY9QjER4ldy4JXZBLA` Nhà Vọng Cảnh: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ17GORdEXQjERhkujx-kwJA0` Khu Du lịch Sinh thái Suối Rạng: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ1XDmcgAZQjERg3z1Ix0EbZA` RAIN MUSIC BOX & GAME: both -> indoor (canonical, conf 0.4) — canonical type/tags (bar, karaoke) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ20P_fAANQjERgFeFcOB6MAs` Điểm đón khách du lịch thuyền thúng cầu Hói Lăng: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau
- `ChIJ244paMwXQjERGVtPeitX4mA` KHU PHỐ DU LỊCH AN THƯỢNG: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ26h5ZAANQjER2otGJosJliA` Rường House - Cooking Class & Craft Workshop: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ27_WHYQXQjERfwDksZnfqKM` TGT BEACH HOTEL: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJ2y5L4dQNQjERxeSLc68fbrw` Ngũ Hành Sơn: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ2zJrN_EXQjERFRsnRcZaDjI` Chợ Chiều: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ3S-Eo0sYQjERo9MhApUI4WQ` Nhà thờ Chính Trạch: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJ4_aypxYZQjERzFP2v0FweY8` Cửa hàng Đặc sản Biển Đà Nẵng: both -> indoor (name, conf 0.6) — name indoor keyword(s) cua hang
- `ChIJ55qx-YAaQjERJm3mA3vFjX0` Chợ Khái Tây: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ5VTV0hwaQjERYReDb0dJJq8` Giáo xứ Cồn Dầu: both -> indoor (canonical, conf 0.4) — canonical type/tags (nha tho) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ5xkIv7EZQjERDZQIupNo09w` Bến Du Thuyền Đà Nẵng: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ5ySJbAAZQjEROESCTb3NJsw` Bến Du Thuyền Sông Hàn: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) song
- `ChIJ6UAZeAAZQjERzK3T81riZmo` Phố đi bộ - chợ đêm Bạch Đằng Đà Nẵng: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ86LzsaUhQjERGxE6itCeBCY` Suối Lương - Hai Van Park: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) park
- `ChIJ8VqGDeYRQjERVEkumiIa714` LÂM TỲ NI VIÊN: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ8Z0D7KURQjERUPd36goDH90` Chùa Tam Tôn: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJ8ai7BQAZQjERIkxmYHcV9DQ` Danang Summer Cooking and Coffee Class: both -> indoor (name, conf 0.6) — name indoor keyword(s) coffee
- `ChIJ8ar-PNQXQjERFGGdrbCAQbg` Tháp Xá Lợi: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ8be7KQARQjER5Lnd2LHaDAs` Huyen Khong Cave: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cave
- `ChIJ9_dffMQQQjERuJbqVGdSysY` Quốc Tự Tam Thai: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ9fqsdOcZQjERZcIMEHw3HtY` Công ty TNHH New Fresh Foods: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJ9w6iligZQjERXLpgwwjF0Fs` Chùa Minh Phước: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJA8a2aLcQQjER5mciBxvjUVs` Chùa Long Hoa: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJASjStc0ZQjERf8hQfCEJ8JA` Chùa An Long: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJAWgMydkZQjER-MpvKFLjoqs` Tiệm cà phê Cậu Út: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJAZn-164ZQjERV1ZAwfTgWuc` Sunny Vietnamese Banh Mi & Coffee Class- Da Nang: both -> indoor (name, conf 0.6) — name indoor keyword(s) coffee
- `ChIJAdChYQAZQjERdBTX1_66Q_8` Chợ Đêm Sơn Trà: outdoor -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJBQHuNG49QjER7Mb_Y2I64mk` Đỉnh Bàn Cờ: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJBT1hHA4XQjERHcTlavRMj5I` Cửa hàng Đặc Sản Đà Nẵng Làm Quà: both -> indoor (name, conf 0.6) — name indoor keyword(s) cua hang
- `ChIJBVvszgofQjER58MnfuhxrRI` Chợ Hòa Liên: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJC0W3bjoYQjERVBMskQcoQck` Di tích Thành Điện Hải: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJCRy3iv_2QTERfZxGJkIMHHQ` Chùa Linh Ứng - Bà Nà: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJCeQZ-jkZQjERaXJSI0ZDWXw` CHÙA KHÔNG TÊN ĐÀ NẴNG: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJDcx-OTIYQjERP4eyjItPspA` Chợ Hàn: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJE4CAepEXQjERg75wrYIZk2Q` Coffee Trà, 51 Lý Đạo Thành, Mân Thái, Sơn Trà, Đà Nẵng: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJEaxZWQAXQjERUp3M2TesuM8` Bãi tắm hàng dừa Mỹ Khê: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJEf1GVMoZQjERQxbPWFvFiKI` Chùa Bát Nhã: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJEymIkTYYQjERWO-pgjkKGMk` Bảo Tàng Đà Nẵng: both -> indoor (name, conf 0.6) — name indoor keyword(s) bao tang
- `ChIJF8yRoecZQjERdDBeBdSRD-Y` DA NANG DOWNTOWN: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJFXRrR0wZQjERNl4jMD9QNFI` Blues Q Coffee and Craft Beer Garden ( Bia thủ công): outdoor -> indoor (name, conf 0.6) — name indoor keyword(s) coffee
- `ChIJFYLgeggZQjERgwxGcK7JcpQ` Tượng đài Mẹ Nhu: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJG1WCi2UXQjER9CxEvEOoEpw` Malibu Beach Club: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) beach
- `ChIJH1ujCM0XQjERcOl1lB9Ns6k` Tuyet Pham Cooking Class: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJH5FAHiEYQjERi-kdX4gd-eE` Đà Nẵng Food Tour: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJHZakNa8ZQjERWNFToM16eB4` Chùa Linh Ứng - Bãi Bụt Sơn Trà: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJI4oSjdE9QjERlXMiA630YKs` Hải đăng Tiên Sa: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJJ2sLdT4YQjERi930NC-XCo0` Nhà Thờ Giáo Xứ Thanh Đức: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJJ93iFIQXQjERhV8dXhMwLOg` A La Carte Danang Beach: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) beach
- `ChIJJYpRy_YXQjERoyNzmnL2f-E` Nhà thờ Thánh Giuse lao công: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJJZ47gFgZQjERvHYpZqPp0lU` Chợ hải sản tươi sống biển Thanh Khê: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) song
- `ChIJJbfHSGUXQjERRXCfzSX3s88` Holiday Beach Hotel Danang: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJJxW4ysUQQjER_NC7GzE1W_0` Meliá Danang Beach Resort: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJK4sVPc0ZQjERdGROWQ8MMg4` Trung Tâm Giải Trí Helio: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJK9EAYgAZQjER_3r0iXAJGLE` Đặc sản Đà Nẵng Phương Châu: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJKbntMIQXQjERh50f5GwfUm4` Sunview Beach Hotel: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJKcik9OQYQjERKZ21jblRTVc` Chùa Thanh Hải: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJKfL8bWgXQjERWPZKseMae6E` Pullman Danang Beach Resort: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJKytgDsgQQjER6al50BDd7vc` Hòn Thủy Sơn: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJL1GKWJYZQjERLrEGqlK2kwQ` Cầu Rồng: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau
- `ChIJLTomluP3QTERUy-b9iAYR8U` Khu du lịch sinh thái Suối Hoa: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJLWoAs80ZQjERLKHDYD-ZymI` Bảo tàng Điêu khắc Chăm Đà Nẵng: both -> indoor (name, conf 0.6) — name indoor keyword(s) bao tang
- `ChIJLX9s7EUbQjERdsy67X5-NrE` Chùa Hải An Đà Nẵng: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJMTadzMQQQjER29xKIZnnHAU` Sandy Beach Non Nuoc Resort: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJMeyhoXgXQjERqCs6CuNR5yI` Sala Danang Beach Hotel: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJN16-6x0fQjERlJytS0E3Kx8` Chợ Quan Nam: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJNQWGShUZQjER71TXPpJW4Xs` Thủ Đạo Thang Spa Đà Nẵng: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJN_abDNcZQjERmLjyrAo7IPk` CẬU ẤM BEER CHILL: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau
- `ChIJNdWwUgARQjERansIEJQleAU` Động Tàng Chơn: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJO0IiWR0RQjERtGkQtqESJ1Y` Động Vân Thông: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJO5_PAj8XQjER34kyBjbMYNo` Family Kitchen Da Nang - Cooking Class: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJO61z6OMZQjERxyCrO6bO28I` Chợ Trời (Flea Market): both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJO9OcO7kQQjERuGR5zEtpfu8` Chùa Thái Sơn: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJOQ-obAARQjERQ4kQhqErSkw` Bãi tắm Nguyễn Thần Hiến: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJOZ__YJwXQjER4wLDpzs9L5c` Chợ Đêm An Thượng: outdoor -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJOfpog-EYQjERw_VB4IBkfNI` Nhà Thờ Giáo Xứ Hòa Minh: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJOxVypBYRQjERMmK2P6JbzF0` Động Âm Phủ: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJOyXC4H0XQjERpm2T2xpZcwU` Chợ An Hải Đông: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJP0--pEAXQjERoheJMf24gHA` Lounge Beach bar & Restaurant: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJP1PH5CMYQjERBYmCltC5WCE` Chợ An Hải Bắc: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJPbgJ4DY9QjER7OSjP2_jSC8` Radar Sơn Trà 1: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJPdLppX4XQjERnV5xcr28sO0` Nhà thờ Gia Phước: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJQ2dbvVIYQjERVbGNKc5Tmcs` CHÙA TÂN THÀNH: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJQWQVKr4ZQjERcafNnRyLelk` DD WONDERLAND: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJQwork9IXQjERVcF8a6VWq5I` Maia Beach Bar: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJRZhHIMkZQjERYBH-5S1xKNg` Chùa Phổ Đà: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJSRWy6Hr3QTERiU3vuI0PbHw` Khu Du Lịch Sinh Thái Lái Thiêu: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJSwMjjYEXQjERBbThTSOPeKY` Siêu thị Đặc sản Hương Đà: both -> indoor (name, conf 0.6) — name indoor keyword(s) sieu thi
- `ChIJT1sjdYQXQjERSLHKKZsmfdQ` Paris Deli Danang Beach Hotel: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJT1zm9U8NQjERQf5DsBriCgc` Dịch Vụ Thuyền Thúng Bến Dừa: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJT9jHPuANQjERQTnqjbIQIF8` Thuyền thúng Dũng Thúy: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJTQo19YMXQjER1DttYZqjHYo` Mandila Beach Hotel: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJUbe6YK4NQjERw6BXx5s8cHM` Rừng Dừa Bảy Mẫu: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) rung
- `ChIJUcRcH40XQjERyj5XPUTEfO0` Hải sản Quang Trường: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) quang truong
- `ChIJVVUC-lEYQjERqdANIT0ShEw` Khách Sạn Smile: both -> indoor (name, conf 0.6) — name indoor keyword(s) khach san
- `ChIJVVmn6uMjQjERwv0F2ZV9pJw` Bãi Sủng Cỏ: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJW7iIXnoXQjERwzVF2LpQ_m4` HAIAN Beach Hotel & Spa: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJW9b8Ky0XQjERPn8CJNdE0Lk` Chùa Mỹ Thị,tổ 11 đường Nguyễn Lữ,quận Ngũ Hành Sơn Thành Phố Đà Nẵng: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJWZ_M9joZQjERLLPsSJV90FY` Chợ Hòa Khánh Nam: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJWaLrVbMZQjERa8YCUGiCkX8` Đặc Sản Chả Bò Bà Tâm Đà Nẵng: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJWe_7hboQQjERxap-mizn-ZY` Nhà bia Chứng tích Núi Ghềnh: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) nui
- `ChIJX7bFNr8NQjERJJLeQ2lyHWo` rừng dừa hội an , basketboat . thuyền thúng Lê Hiền: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) rung
- `ChIJX_rcYHQZQjERQXQ9UxHmHN4` Nhà Thờ Giáo Xứ Phước Tường: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJXcxl0UcYQjERVfYu-bKtvPU` Chợ Thanh Bình: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJXxYRdgAZQjERUsI1RdpUQtc` Sơn Trà/ Đà Nẵng: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJY3yT3IweQjERnbDRpKk8b3A` Nhà thờ Phú Thượng: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJYcrN5SQaQjERbT7ApRUexlQ` Đặc sản Đà Nẵng - Bánh khô mè Bà Liễu Mẹ làm quà tặng: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJYyr_6ogXQjERoXAq8cGEzcI` Rose Da Nang Coffee Workshop: both -> indoor (name, conf 0.6) — name indoor keyword(s) coffee
- `ChIJZ6w1fJgZQjERP9-_TlpgQXM` Lagoon Rooftop - Dragon Bridge Fire Show: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) bridge
- `ChIJ_XkaoQs-QjER_IUTHqI3gI8` Mũi Nghê: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJaQNtm9IfQjERhfrVRYqgA1M` Hồ Hòa Trung: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJaUuo57kZQjERzjJfr1YdjCA` Chùa Báo Ân: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJaV_Jo8gZQjERtDWMcdLRT1U` Nhà Thờ Giáo Xứ Hòa Thuận: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJaX09zkgYQjERCtro2DeADN0` Chùa Thuận Thành: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJabEOcucXQjER-8MNU9FNODw` Tượng Quan Thế Âm Bồ Tát: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJb-kmpPQXQjERKc6w6X8CFKc` Chợ Mân Thái: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJbVtm0WIfQjER_HG2AYprbcY` Nhà Vân Tiểu: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJcw0FdkgYQjERhr14f9cMXK0` Nhà Thờ Giáo Xứ Nội Hà: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJd8h2AyoRQjERNWCSTs1L1jU` Vive Océane - Beach Club & Restaurant: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJddXz2K8PQjER4enhapQvvo8` Cooking With Jolie In Hoi An – Vietnamese Cooking Class: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJeaPwiDUYQjERt4yUm81Oqi8` Khu Ẩm Thực Chợ Cồn -식사 공간: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJfQNjLMYQQjERo1m_A0X8aLE` Chùa Non Nước: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJf_LKvbkbQjERSVrbzxU6Nuc` Chùa Vân Long: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJg2m14V0ZQjERt4DjGOdJDiE` Jolie Cooking Class: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJg4XJWVkZQjERVOuuY25EzR0` Chả Bò Bà Yến – Đặc Sản Đà Nẵng Làm Quà: both -> indoor (canonical, conf 0.4) — canonical type/tags (nha hang, cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJg5OvAgAhQjERKbrq9-Wza-U` Khu Du Lịch Sinh Thái Thuỷ Vân Sơn: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJg5P0rjoZQjER1MD61JUxPB0` Chợ Hòa Khánh: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJgaLldI0ZQjEReQCfThP_6CQ` Công viên Kỳ Quan: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cong vien
- `ChIJkatEeMwZQjERnAUKgmrbNgQ` Làng Bích họa Đà Nẵng: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJl21Hd_4YQjERF980f9HS9Cc` Chùa Làng Thanh Khê: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJlU7ZlygfQjERs_tFa6tFx-s` Chợ Thanh Vinh: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJlZA7YgEZQjERwBfzBwsUo18` Đặc sản Đà Nẵng làm quà - Dương Lê: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJlxydWJEZQjER5GSMuHJHtak` VỌC Glamping: both -> indoor (canonical, conf 0.4) — canonical type/tags (nha hang, ca phe, khach san) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJm2iwgggbQjERj-x6QTYemFQ` Shop Hoa Tươi Quận Ngũ Hành Sơn Đà Nẵng | Điện Hoa Đà Nẵng: both -> indoor (name, conf 0.6) — name indoor keyword(s) shop
- `ChIJmU3hl9WrNTERBUbnSp3g5vs` Thuan Tinh Island Cooking Tour: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) island
- `ChIJmUEOJQAfQjERLPIN_eYfU9k` Khu du lịch Nam Ô Heritage: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJnZoMTbkQQjERwzvvHqGlb4E` Chùa Linh Sơn: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJnwKLiE4YQjERMVI0qrqKg1c` Nhà Thờ Giáo Xứ Tam Tòa: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJo2Yyix8ZQjERmG7AHQkOpIo` Chùa Phước Lộc: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJo8N_zUw9QjERgutJ9u3-n7Y` View Ngắm Bình Minh Sơn Trà: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJp3BwHgsZQjERzQZfxwNQNmE` Chùa Làng Thanh Khê: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJp91wYRgZQjER9Yry1HWPhW8` Du thuyền sông Hàn Vinh Anh - Da Nang cruise on Han river: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) song, river
- `ChIJp9cNzfwZQjERS7ZSaA95etk` Danang Cooking Class - Lá Sen ダナン料理教室: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJpRFvp6sZQjERY_CDfnMCx2w` Vigift Đà Nẵng – Quà Đặc Sản | Souvenir & Speciality | 기념품 & 특산품: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJpYNhNwAXQjERflfHrn1lop4` Vịnh Sơn Trà: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJpeV7WwAZQjER5TfSiKGu0Qc` Cô Na - ĐẶC SẢN ĐÀ NẴNG: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJq7Uto10fQjERQgZQB_w3cBw` Cổng Chào Khu Công Nghệ Cao Đà Nẵng: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJr-RyTyYfQjERmXNNs1WNyY4` cafe phố núi: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJrQINf-wZQjEREXiFm4Gq56M` Da Nang Family Cooking Class: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJrW03HQAXQjERLRu5Xd4RvsE` Seavitel Beach Hotel - DaNang: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJr_MgSAAZQjERnbnJDAtASZM` Chill Beach Thanh Khê: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) beach
- `ChIJrd3YeXENQjERWWbMPMdY2CE` Tham Quan Rừng Dừa Bảy Mẫu - Thuyền Thúng Hội An: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) rung
- `ChIJrfvtnpYhQjEReNe0fgh8KMM` Chùa Nam Hải: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJrxxvlNsXQjERy-eJcpABRJA` Nhu Minh Plaza Danang Hotel: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJrynevMsZQjERzZIGoLZwQ2I` Chùa Từ Tôn: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJs-NDcgAXQjERHA6tioqOfH4` Apron Up Cooking Class in Danang: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJs4dg5vceQjERJQ5D9ATvWhU` NHÀ THỜ CỔ TÙNG SƠN - NHÀ THỜ CÔNG GIÁO: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJs5puLQA9QjERIaHbrBAGpjA` Dịch Vụ Cano Du Lịch Lặn Biển Ngắm San Hô Sơn Trà: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJsVPjaP8YQjER76Ao_3tvppY` Chùa Thanh Hà: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJsdeOrV8XQjER8weQ8Az-w5c` Chùa Bà Đa: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJsyY9JzoYQjERvaNXwl9KJkI` Spa Massage Sông Hàn: indoor -> unknown (name, conf 0.3) — name keywords conflict -> unknown
- `ChIJu59e1rsRQjERB-49hSxMnXo` Bãi Tắm Non Nước: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJu5AYG0UXQjEREoejRui0VzY` Đặc Sản Ngon Đà Nẵng - Đặc Sản Làm Quà shop online: both -> indoor (name, conf 0.6) — name indoor keyword(s) shop
- `ChIJu6FQjzUYQjER39TMpgQVRUs` Chợ Cồn: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJuaI3VgMZQjER0B4a7LcJ-YA` Nhà Thờ Giáo Xứ An Hòa: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJuzUYUgAXQjER7uqAcJPQMY0` Cổng Chùa Linh Ứng: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJuzoag4EXQjERm__A5Whnw5I` Chùa Mỹ Khê: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJuzvMeE4ZQjERE-pQycR-Mjo` Cầu vượt đi bộ Mikazuki: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau
- `ChIJvexouL4QQjERy0qt57A0GX4` Chùa Phổ Đà Sơn: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJw6DOwZ8QQjERjDMobkQxbF0` Chợ Bình Kỳ: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJwandNwA9QjERWjnwsYXsQrk` Nhất Lâm Thủy Trang Trà: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJx0dBXWYNQjERQzQO18QYhas` Mimi Cooking Class: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJxU52AgAZQjERUmuAje5_L5Q` Bãi biển Nguyễn Tất Thành: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) bai bien
- `ChIJxdBK6SsYQjERYojL_cVEkbs` Nhà thờ Giáo xứ An Hải: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `ChIJy9eI3pEZQjERRjXgQMj8m-g` Mê Vui - Đặc sản Đà Nẵng SẠCH: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJyUQ4aw72QTERCXl5YV-4U1w` Sun World Bà Nà Hills: both -> outdoor (canonical, conf 0.4) — canonical type/tags (cong vien) -> outdoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJyWFmArX3QTERon6tUT6re4Q` Ba Na Hills: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJyZOJHa8NQjERSvp9yMenV6Y` Vinh Vo Cooking Class: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `ChIJyaniiLoQQjERI3aW6z5atCc` Chùa Hương Sơn: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `ChIJyd-t1B0ZQjERVSYFtVbYms8` Thiền Viện Bồ Đề: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJye8yM0M9QjERwtla0qUFoOs` Hải sản tươi sống Bà Rô: indoor -> outdoor (name, conf 0.6) — name outdoor keyword(s) song
- `ChIJzUoWGdQXQjEReYmzPE0JBDw` Tượng Phật Nhập Niết Bàn: both -> indoor (canonical, conf 0.4) — canonical type/tags (chua) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `manual:cu-lao-cham` Cù Lao Chàm: both -> outdoor (canonical, conf 0.4) — canonical type/tags (dao) -> outdoor (heuristic default) [conf 0.4, uncalibrated]
- `manual:hai-van-quan` Hải Vân Quan: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `manual:vinwonders-nam-hoi-an` VinWonders Nam Hội An: both -> outdoor (canonical, conf 0.4) — canonical type/tags (cong vien) -> outdoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/10154412164` Fantasy Park: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) park
- `osm:node/1036552571` Đèo Hải Vân: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) deo
- `osm:node/10603622205` Pont main: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/10709724107` Làng đá mỹ nghệ Non Nước: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/10709738005` Làng chiếu Cẩm Nê: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/10709738105` Làng nước mắm Nam Ô: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/10723988763` Đài tưởng niệm thảm sát Hà My: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/11161070775` Dragon's Head: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/11359603957` Chùa Nam Sơn: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/11427582964` Thai Market: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/11832500969` Rào chắn: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/11888483369` Chợ Phước Mỹ: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/11934169470` Queen Cobra: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/12333995781` Chợ đêm Lê Duẩn: outdoor -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/12404434601` Khu Văn hóa Tâm linh Đà Sơn: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/12603319867` Nhà thờ Thanh Bình: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `osm:node/12701675501` Small waterfall: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) waterfall
- `osm:node/12811972501` Mart Souvenir: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/13008480396` Miếu xóm: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/13293564930` Himawari: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/1335374752` miếu Thần Nông: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/1335374809` chùa am Nam Ngư: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/1335374818` miếu Ngài Ngư: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/1335374858` chùa am thờ Hỏa Xa: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/1335374873` chùa An Cư Tây: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/1335374895` miếu Âm Hồn: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/13484040419` Đền Bà Càn Khôn: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/13677406601` Memorial to the victims of the Flight 229 plane crash on March 15, 1979.: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/13687068650` Linh Phong Bảo Tháp: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/13734880501` Tượng Phật Phước Lý: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/14045110791` Lucky Retail: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/14045130739` Made in Vietnam: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/14045144381` Viet Nam's Delights: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/14067929701` Bonny handmade: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/14130293535` Tượng đài Dũng sĩ Điện Ngọc: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/2177056870` Thác Tóc Tiên: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) thac
- `osm:node/3760247201` chùa Vu Lan: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/3760247202` chùa Sư Nữ: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/3760272162` Chùa Tam Bảo: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/3763846156` Chùa Pháp Lâm: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/4005611262` Đền thờ Tiền Hiền làng Lổ Giang: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/4005611263` Đình Lổ Giáng: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/4172034499` Non Nuoc Beach: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) beach
- `osm:node/4280016689` Chùa Giác Hoàng Viên: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/4294135790` nhà thờ Phú Thượng: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `osm:node/4294139091` nhà thờ An Ngãi Tây: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `osm:node/4294143691` Nhà thờ Giáo xứ An Thượng: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `osm:node/4294167889` nhà thờ Tùng Sơn: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `osm:node/4386676224` Chợ Miếu Bông: both -> unknown (canonical, conf 0.4) — canonical cat=market is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/4706189591` To Quoc Ghi Cong: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/4741642219` Public beach: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) beach
- `osm:node/4845297821` Gần núi thần tài: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) nui
- `osm:node/4924323121` Fishing Village and Fleet: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/5273998822` Cầu Tiên Sơn: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau
- `osm:node/5273998823` Cầu Trần Thị Lý: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau
- `osm:node/5273999121` Cầu Thuận Phước: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau
- `osm:node/5276547123` Cau Nguyen Van Troi Bridge: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau, bridge
- `osm:node/5286977425` Núi Thần Tài: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) nui
- `osm:node/5421670780` Chùa An Phước: both -> indoor (name, conf 0.6) — name indoor keyword(s) chua
- `osm:node/5432701004` Nhà thờ Hoà Cường: both -> indoor (name, conf 0.6) — name indoor keyword(s) nha tho
- `osm:node/6332518185` Miếu Xóm An Mỹ: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/6346486685` Cây đa đại thụ: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/6369465978` Vietnamese Mother Statue: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/6513792708` Đình Phục Đán: both -> unknown (canonical, conf 0.4) — canonical cat=landmark is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/6528451001` Cây đa Đò Xu: both -> unknown (canonical, conf 0.4) — canonical cat=attraction is ambiguous -> unknown [conf 0.4, uncalibrated]
- `osm:node/7095169369` Non La: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/7276380289` Cầu Sông Hàn: both -> outdoor (name, conf 0.6) — name outdoor keyword(s) cau, song
- `osm:node/7477670190` 노니판매점: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/7477670191` Gio coffee: both -> indoor (name, conf 0.6) — name indoor keyword(s) coffee
- `osm:node/9921282483` Viet Nam's Delights: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/9921315929` Lưu Niệm - Đặc Sản: both -> indoor (canonical, conf 0.4) — canonical type/tags (cua hang) -> indoor (heuristic default) [conf 0.4, uncalibrated]

## Conflict IDs

ChIJ0-6wNdsXQjER068QxYa3E5o, ChIJ27_WHYQXQjERfwDksZnfqKM, ChIJAWgMydkZQjER-MpvKFLjoqs, ChIJE4CAepEXQjERg75wrYIZk2Q, ChIJJbfHSGUXQjERRXCfzSX3s88, ChIJJxW4ysUQQjER_NC7GzE1W_0, ChIJKbntMIQXQjERh50f5GwfUm4, ChIJKfL8bWgXQjERWPZKseMae6E, ChIJM5BHkDAZQjERYlaJyu15KFg, ChIJMTadzMQQQjER29xKIZnnHAU, ChIJMeyhoXgXQjERqCs6CuNR5yI, ChIJNQWGShUZQjER71TXPpJW4Xs, ChIJP0--pEAXQjERoheJMf24gHA, ChIJQwork9IXQjERVcF8a6VWq5I, ChIJT1sjdYQXQjERSLHKKZsmfdQ, ChIJTQo19YMXQjER1DttYZqjHYo, ChIJW7iIXnoXQjERwzVF2LpQ_m4, ChIJd8h2AyoRQjERNWCSTs1L1jU, ChIJr-RyTyYfQjERmXNNs1WNyY4, ChIJrW03HQAXQjERLRu5Xd4RvsE, ChIJrcJ8wVwRQjERJF58LAQEO-I, ChIJrxxvlNsXQjERy-eJcpABRJA, ChIJsyY9JzoYQjERvaNXwl9KJkI
