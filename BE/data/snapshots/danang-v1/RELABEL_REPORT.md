# T063 weather relabel report

- Tool version: `t063b-weather-exposure-v1`
- Generated (UTC): 2026-10-21
- POIs: 764
- Audit labels applied: 46
- Audit labels preserved exactly: 46
- Changed space labels: 132
- Changed rain-protection labels: 0
- Unique POIs with a changed weather label: 132
- Review rows: 200

## Space transitions (old -> new)

- `both->both`: 5
- `indoor->both`: 76
- `indoor->indoor`: 477
- `outdoor->both`: 1
- `outdoor->indoor`: 2
- `outdoor->outdoor`: 83
- `unknown->both`: 23
- `unknown->indoor`: 22
- `unknown->outdoor`: 8
- `unknown->unknown`: 67

### Space sources

| key | count |
|---|---|
| audit | 46 |
| canonical | 236 |
| name | 467 |
| osm | 15 |

### Space confidence

| key | count |
|---|---|
| 0.4 | 236 |
| 0.6 | 467 |
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

- `ChIJ-cf9B7wQQjERutUzeynzw8w` Chùa Quán Thế Âm: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJ0-6wNdsXQjER068QxYa3E5o` Karaoke Song Ca: unknown -> indoor (name, conf 0.6) — name venue keyword(s) karaoke beat descriptive outdoor keyword(s) song -> indoor
- `ChIJ1XDmcgAZQjERg3z1Ix0EbZA` RAIN MUSIC BOX & GAME: indoor -> both (canonical, conf 0.4) — canonical type/tags (cho) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ27_WHYQXQjERfwDksZnfqKM` TGT BEACH HOTEL: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJ2exBne0ZQjERj07NR6zFg4c` MÊ Ê Ê Beer Garden - 316 Hà Huy Tập: indoor -> both (name, conf 0.6) — name compound keyword(s) beer garden -> both
- `ChIJ2zJrN_EXQjERFRsnRcZaDjI` Chợ Chiều: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJ3S-Eo0sYQjERo9MhApUI4WQ` Nhà thờ Chính Trạch: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJ55qx-YAaQjERJm3mA3vFjX0` Chợ Khái Tây: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJ5VTV0hwaQjERYReDb0dJJq8` Giáo xứ Cồn Dầu: indoor -> both (canonical, conf 0.4) — canonical type/tags (nha tho) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ6UAZeAAZQjERzK3T81riZmo` Phố đi bộ - chợ đêm Bạch Đằng Đà Nẵng: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJ8VqGDeYRQjERVEkumiIa714` LÂM TỲ NI VIÊN: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ8Z0D7KURQjERUPd36goDH90` Chùa Tam Tôn: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJ8ar-PNQXQjERFGGdrbCAQbg` Tháp Xá Lợi: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ9_dffMQQQjERuJbqVGdSysY` Quốc Tự Tam Thai: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJ9w6iligZQjERXLpgwwjF0Fs` Chùa Minh Phước: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJA0bFwKoZQjER--pX5_3_cD0` Tú Chợ đêm: indoor -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJA8a2aLcQQjER5mciBxvjUVs` Chùa Long Hoa: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJASjStc0ZQjERf8hQfCEJ8JA` Chùa An Long: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJAWgMydkZQjER-MpvKFLjoqs` Tiệm cà phê Cậu Út: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) ca phe
- `ChIJAdChYQAZQjERdBTX1_66Q_8` Chợ Đêm Sơn Trà: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJBVvszgofQjER58MnfuhxrRI` Chợ Hòa Liên: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJCRy3iv_2QTERfZxGJkIMHHQ` Chùa Linh Ứng - Bà Nà: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJCeQZ-jkZQjERaXJSI0ZDWXw` CHÙA KHÔNG TÊN ĐÀ NẴNG: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJDcx-OTIYQjERP4eyjItPspA` Chợ Hàn: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJE4CAepEXQjERg75wrYIZk2Q` Coffee Trà, 51 Lý Đạo Thành, Mân Thái, Sơn Trà, Đà Nẵng: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) coffee
- `ChIJEaxZWQAXQjERUp3M2TesuM8` Bãi tắm hàng dừa Mỹ Khê: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) bai tam
- `ChIJEf1GVMoZQjERQxbPWFvFiKI` Chùa Bát Nhã: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJFXRrR0wZQjERNl4jMD9QNFI` Blues Q Coffee and Craft Beer Garden ( Bia thủ công): indoor -> both (name, conf 0.6) — name compound keyword(s) beer garden -> both
- `ChIJFYLgeggZQjERgwxGcK7JcpQ` Tượng đài Mẹ Nhu: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) tuong dai
- `ChIJHZakNa8ZQjERWNFToM16eB4` Chùa Linh Ứng - Bãi Bụt Sơn Trà: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJJ2sLdT4YQjERi930NC-XCo0` Nhà Thờ Giáo Xứ Thanh Đức: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJJYpRy_YXQjERoyNzmnL2f-E` Nhà thờ Thánh Giuse lao công: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJJZ47gFgZQjERvHYpZqPp0lU` Chợ hải sản tươi sống biển Thanh Khê: outdoor -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJJbfHSGUXQjERRXCfzSX3s88` Holiday Beach Hotel Danang: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJJxW4ysUQQjER_NC7GzE1W_0` Meliá Danang Beach Resort: unknown -> indoor (name, conf 0.6) — name venue keyword(s) resort beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJKbntMIQXQjERh50f5GwfUm4` Sunview Beach Hotel: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJKcik9OQYQjERKZ21jblRTVc` Chùa Thanh Hải: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJKfL8bWgXQjERWPZKseMae6E` Pullman Danang Beach Resort: unknown -> indoor (name, conf 0.6) — name venue keyword(s) resort beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJLX9s7EUbQjERdsy67X5-NrE` Chùa Hải An Đà Nẵng: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJMTadzMQQQjER29xKIZnnHAU` Sandy Beach Non Nuoc Resort: unknown -> indoor (name, conf 0.6) — name venue keyword(s) resort beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJMeyhoXgXQjERqCs6CuNR5yI` Sala Danang Beach Hotel: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJN16-6x0fQjERlJytS0E3Kx8` Chợ Quan Nam: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJNQWGShUZQjER71TXPpJW4Xs` Thủ Đạo Thang Spa Đà Nẵng: unknown -> indoor (name, conf 0.6) — name indoor keyword(s) spa
- `ChIJN_abDNcZQjERmLjyrAo7IPk` CẬU ẤM BEER CHILL: outdoor -> indoor (canonical, conf 0.4) — canonical cat=restaurant -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJNdWwUgARQjERansIEJQleAU` Động Tàng Chơn: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJO61z6OMZQjERxyCrO6bO28I` Chợ Trời (Flea Market): unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJO9OcO7kQQjERuGR5zEtpfu8` Chùa Thái Sơn: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJOQ-obAARQjERQ4kQhqErSkw` Bãi tắm Nguyễn Thần Hiến: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) bai tam
- `ChIJOZ__YJwXQjER4wLDpzs9L5c` Chợ Đêm An Thượng: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJOfpog-EYQjERw_VB4IBkfNI` Nhà Thờ Giáo Xứ Hòa Minh: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJOxVypBYRQjERMmK2P6JbzF0` Động Âm Phủ: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJOyXC4H0XQjERpm2T2xpZcwU` Chợ An Hải Đông: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJP0--pEAXQjERoheJMf24gHA` Lounge Beach bar & Restaurant: unknown -> indoor (name, conf 0.6) — name venue keyword(s) restaurant, bar beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJP1PH5CMYQjERBYmCltC5WCE` Chợ An Hải Bắc: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJPdLppX4XQjERnV5xcr28sO0` Nhà thờ Gia Phước: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJQ2dbvVIYQjERVbGNKc5Tmcs` CHÙA TÂN THÀNH: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJQwork9IXQjERVcF8a6VWq5I` Maia Beach Bar: unknown -> indoor (name, conf 0.6) — name venue keyword(s) bar beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJRZhHIMkZQjERYBH-5S1xKNg` Chùa Phổ Đà: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJT1sjdYQXQjERSLHKKZsmfdQ` Paris Deli Danang Beach Hotel: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJTQo19YMXQjER1DttYZqjHYo` Mandila Beach Hotel: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJUdH0Q88ZQjER0AoQ8Pbil28` Nia Coffee: indoor -> both (osm, conf 0.7) — OSM node/13744719202 explicit indoor+outdoor evidence (element); name indoor keyword(s) coffee
- `ChIJVWzfhcwZQjERa_qP0BpsBkk` Nhà thờ Tộc Hồ Thanh Khê: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJW7iIXnoXQjERwzVF2LpQ_m4` HAIAN Beach Hotel & Spa: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel, spa beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJW9b8Ky0XQjERPn8CJNdE0Lk` Chùa Mỹ Thị,tổ 11 đường Nguyễn Lữ,quận Ngũ Hành Sơn Thành Phố Đà Nẵng: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJWZ_M9joZQjERLLPsSJV90FY` Chợ Hòa Khánh Nam: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJX_rcYHQZQjERQXQ9UxHmHN4` Nhà Thờ Giáo Xứ Phước Tường: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJXcxl0UcYQjERVfYu-bKtvPU` Chợ Thanh Bình: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJY3yT3IweQjERnbDRpKk8b3A` Nhà thờ Phú Thượng: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJaQNtm9IfQjERhfrVRYqgA1M` Hồ Hòa Trung: unknown -> indoor (osm, conf 0.7) — OSM node/5255590921 indoor category tags
- `ChIJaUuo57kZQjERzjJfr1YdjCA` Chùa Báo Ân: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJaV_Jo8gZQjERtDWMcdLRT1U` Nhà Thờ Giáo Xứ Hòa Thuận: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJaX09zkgYQjERCtro2DeADN0` Chùa Thuận Thành: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJabEOcucXQjER-8MNU9FNODw` Tượng Quan Thế Âm Bồ Tát: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJb-kmpPQXQjERKc6w6X8CFKc` Chợ Mân Thái: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJcw0FdkgYQjERhr14f9cMXK0` Nhà Thờ Giáo Xứ Nội Hà: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJd8h2AyoRQjERNWCSTs1L1jU` Vive Océane - Beach Club & Restaurant: unknown -> indoor (name, conf 0.6) — name venue keyword(s) restaurant beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJeaPwiDUYQjERt4yUm81Oqi8` Khu Ẩm Thực Chợ Cồn -식사 공간: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJfQNjLMYQQjERo1m_A0X8aLE` Chùa Non Nước: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJf_LKvbkbQjERSVrbzxU6Nuc` Chùa Vân Long: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJg5P0rjoZQjER1MD61JUxPB0` Chợ Hòa Khánh: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJl21Hd_4YQjERF980f9HS9Cc` Chùa Làng Thanh Khê: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJlU7ZlygfQjERs_tFa6tFx-s` Chợ Thanh Vinh: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJlxydWJEZQjER5GSMuHJHtak` VỌC Glamping: indoor -> both (canonical, conf 0.4) — canonical type/tags (cho) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJnZoMTbkQQjERwzvvHqGlb4E` Chùa Linh Sơn: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJnwKLiE4YQjERMVI0qrqKg1c` Nhà Thờ Giáo Xứ Tam Tòa: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJo2Yyix8ZQjERmG7AHQkOpIo` Chùa Phước Lộc: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJp3BwHgsZQjERzQZfxwNQNmE` Chùa Làng Thanh Khê: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJr-RyTyYfQjERmXNNs1WNyY4` cafe phố núi: unknown -> indoor (name, conf 0.6) — name venue keyword(s) cafe beat descriptive outdoor keyword(s) nui -> indoor
- `ChIJrW03HQAXQjERLRu5Xd4RvsE` Seavitel Beach Hotel - DaNang: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) beach -> indoor
- `ChIJrfvtnpYhQjEReNe0fgh8KMM` Chùa Nam Hải: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJrxxvlNsXQjERy-eJcpABRJA` Nhu Minh Plaza Danang Hotel: unknown -> indoor (name, conf 0.6) — name venue keyword(s) hotel beat descriptive outdoor keyword(s) plaza -> indoor
- `ChIJrynevMsZQjERzZIGoLZwQ2I` Chùa Từ Tôn: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJs4dg5vceQjERJQ5D9ATvWhU` NHÀ THỜ CỔ TÙNG SƠN - NHÀ THỜ CÔNG GIÁO: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJsVPjaP8YQjER76Ao_3tvppY` Chùa Thanh Hà: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJsdeOrV8XQjER8weQ8Az-w5c` Chùa Bà Đa: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJsyY9JzoYQjERvaNXwl9KJkI` Spa Massage Sông Hàn: unknown -> indoor (name, conf 0.6) — name venue keyword(s) spa beat descriptive outdoor keyword(s) song -> indoor
- `ChIJu59e1rsRQjERB-49hSxMnXo` Bãi Tắm Non Nước: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) bai tam
- `ChIJu6FQjzUYQjER39TMpgQVRUs` Chợ Cồn: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJuaI3VgMZQjER0B4a7LcJ-YA` Nhà Thờ Giáo Xứ An Hòa: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJuzUYUgAXQjER7uqAcJPQMY0` Cổng Chùa Linh Ứng: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJuzoag4EXQjERm__A5Whnw5I` Chùa Mỹ Khê: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJvexouL4QQjERy0qt57A0GX4` Chùa Phổ Đà Sơn: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJw6DOwZ8QQjERjDMobkQxbF0` Chợ Bình Kỳ: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `ChIJxdBK6SsYQjERYojL_cVEkbs` Nhà thờ Giáo xứ An Hải: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `ChIJyaniiLoQQjERI3aW6z5atCc` Chùa Hương Sơn: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `ChIJyd-t1B0ZQjERVSYFtVbYms8` Thiền Viện Bồ Đề: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `ChIJye8yM0M9QjERwtla0qUFoOs` Hải sản tươi sống Bà Rô: outdoor -> indoor (canonical, conf 0.4) — canonical cat=restaurant -> indoor (heuristic default) [conf 0.4, uncalibrated]
- `ChIJzUoWGdQXQjEReYmzPE0JBDw` Tượng Phật Nhập Niết Bàn: indoor -> both (canonical, conf 0.4) — canonical type/tags (chua) -> both (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/10723988763` Đài tưởng niệm thảm sát Hà My: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) dai tuong niem
- `osm:node/11359603957` Chùa Nam Sơn: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/11427582964` Thai Market: unknown -> both (canonical, conf 0.4) — canonical type/tags (cho) -> both (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/11888483369` Chợ Phước Mỹ: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `osm:node/12333995781` Chợ đêm Lê Duẩn: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `osm:node/12603319867` Nhà thờ Thanh Bình: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `osm:node/1335374809` chùa am Nam Ngư: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/1335374858` chùa am thờ Hỏa Xa: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/1335374873` chùa An Cư Tây: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/13677406601` Memorial to the victims of the Flight 229 plane crash on March 15, 1979.: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) memorial
- `osm:node/14130293535` Tượng đài Dũng sĩ Điện Ngọc: unknown -> outdoor (name, conf 0.6) — name outdoor keyword(s) tuong dai
- `osm:node/3760247201` chùa Vu Lan: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/3760247202` chùa Sư Nữ: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/3760272162` Chùa Tam Bảo: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/3763846156` Chùa Pháp Lâm: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/4280016689` Chùa Giác Hoàng Viên: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/4294135790` nhà thờ Phú Thượng: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `osm:node/4294139091` nhà thờ An Ngãi Tây: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `osm:node/4294143691` Nhà thờ Giáo xứ An Thượng: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `osm:node/4294167889` nhà thờ Tùng Sơn: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both
- `osm:node/4386676224` Chợ Miếu Bông: unknown -> both (name, conf 0.6) — name compound keyword(s) cho -> both
- `osm:node/4706189591` To Quoc Ghi Cong: unknown -> outdoor (canonical, conf 0.4) — canonical type/tags (tuong dai) -> outdoor (heuristic default) [conf 0.4, uncalibrated]
- `osm:node/5421670780` Chùa An Phước: indoor -> both (name, conf 0.6) — name compound keyword(s) chua -> both
- `osm:node/5432701004` Nhà thờ Hoà Cường: indoor -> both (name, conf 0.6) — name compound keyword(s) nha tho -> both

## Conflict IDs

ChIJBcr6kegZQjER2nCllYpT_Qc, ChIJFad1TFAXQjERE9B6U1THHT4, ChIJM5BHkDAZQjERYlaJyu15KFg, ChIJO56jTAARQjEREYLpKFOB1DA, ChIJP1Uz6i0ZQjERfy-rpM1cGWc, ChIJqSwlvMkZQjERE_9aVr3pkes, ChIJrcJ8wVwRQjERJF58LAQEO-I, ChIJz0Od5IUXQjERmAV9JgLRqm8
