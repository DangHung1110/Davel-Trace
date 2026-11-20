# Task for Codex — 2 lookups (read pages only, do not guess)

Write ONE file: `reports/p0/links/final2_codex.json`. Do not edit any other file. Do not commit.
Use a generic User-Agent `davel-trace-data/0.1`. Quote the exact sentence from each page you read.

## 1. Asia Park / Công viên Châu Á = "Da Nang Downtown" (Sun World), OSM way/667422708 (16.0412218,108.2263899)
Read https://sunworld.vn/da-nang-downtown (and the sunworld.vn ticket/hours page if linked), plus
https://mytour.vn/vi/blog/bai-viet/da-nang-wonderland-huong-dan-trai-nghiem-tu-a-den-z.html
Answer: is it operating now (2026)? opening hours (weekday / weekend)? entry fee (free gate?) and ride/Sun Wheel prices?
Also the best entrance coordinate if a page gives one.

## 2. Bến CT15, đường Hoàng Sa, phường Thọ Quang, Sơn Trà, Đà Nẵng (cano/coral diving tour departure pier)
Find coordinates (WGS84) from a page you actually read (OSM/Nominatim/Overpass, or a tour page with lat/lon or a Google Maps link with coordinates).
Also read https://oktrip.vn/du-lich-tu-tuc/trai-nghiem-lan-ngam-san-ho-da-nang/ and confirm: departures 8h00–14h45, 120 minutes, adult 450.000, child 1–6 250.000.

## Output schema
{"asia_park": {"operating": bool|null, "hours": "...", "weekend_hours": "...", "entry": "...", "prices": "...", "lat": null, "lon": null, "sources": [{"url": "...", "quote": "..."}]},
 "ct15": {"lat": null, "lon": null, "confidence": "high|medium|low", "sources": [...], "oktrip_confirms": bool|null, "oktrip_quote": "..."}}
Use null where no page states it.
