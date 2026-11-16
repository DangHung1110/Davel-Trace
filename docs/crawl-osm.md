# Hướng dẫn lấy POI Đà Nẵng từ OpenStreetMap

Tài liệu này hướng dẫn tải các địa điểm (POI) như nhà hàng, quán cà phê, khách sạn và điểm tham quan tại Đà Nẵng để phục vụ thử nghiệm tạo lịch trình.

## 1. API sử dụng

Dùng **Overpass API**:

```text
https://overpass-api.de/api/interpreter
```

- Không cần API key.
- Không dùng Nominatim để tải toàn bộ POI. Nominatim chủ yếu dành cho tìm kiếm địa chỉ và không cho phép tải POI hàng loạt từ server công cộng.
- Server Overpass công cộng chỉ phù hợp để thử nghiệm hoặc tải không thường xuyên. Không gửi nhiều request song song.

## 2. Truy vấn POI Đà Nẵng

Có thể dán truy vấn sau vào <https://overpass-turbo.eu/> để xem kết quả trước:

```overpass
[out:json][timeout:180];

area
  ["boundary"="administrative"]
  ["name"="Đà Nẵng"]
  ["admin_level"="4"]
  ->.danang;

(
  // Nhà hàng, quán ăn và quán cà phê
  nwr["amenity"~"^(restaurant|cafe|fast_food|food_court|bar|pub|ice_cream)$"](area.danang);

  // Khách sạn và điểm tham quan
  nwr["tourism"~"^(hotel|hostel|guest_house|motel|resort|attraction|museum|gallery|viewpoint|theme_park|zoo|information)$"](area.danang);

  // Vui chơi, giải trí
  nwr["leisure"~"^(park|water_park|sports_centre|stadium|swimming_pool|fitness_centre|amusement_arcade)$"](area.danang);

  // Văn hóa và lịch sử
  nwr["historic"](area.danang);
  nwr["amenity"="place_of_worship"](area.danang);
  nwr["amenity"~"^(theatre|cinema|arts_centre)$"](area.danang);

  // Thiên nhiên
  nwr["natural"~"^(beach|peak|cave_entrance|spring|waterfall)$"](area.danang);

  // Mua sắm
  nwr["shop"~"^(mall|department_store|supermarket|gift|souvenir)$"](area.danang);
  nwr["amenity"="marketplace"](area.danang);
);

out center;
```

`nwr` lấy cả ba loại đối tượng OpenStreetMap:

- `node`: địa điểm dạng điểm.
- `way`: tòa nhà hoặc khu vực.
- `relation`: khu vực hoặc đối tượng phức hợp.

`out center` bổ sung tọa độ tâm cho `way` và `relation` để có thể đặt marker lên bản đồ.

## 3. Tải dữ liệu bằng PowerShell

Mở PowerShell tại thư mục dự án rồi chạy:

```powershell
$query = @'
[out:json][timeout:180];

area
  ["boundary"="administrative"]
  ["name"="Đà Nẵng"]
  ["admin_level"="4"]
  ->.danang;

(
  nwr["amenity"~"^(restaurant|cafe|fast_food|food_court|bar|pub)$"](area.danang);
  nwr["tourism"~"^(hotel|hostel|guest_house|motel|resort|attraction|museum|gallery|viewpoint)$"](area.danang);
  nwr["leisure"~"^(park|water_park|sports_centre|stadium|swimming_pool)$"](area.danang);
  nwr["historic"](area.danang);
  nwr["natural"~"^(beach|peak|cave_entrance|waterfall)$"](area.danang);
);

out center;
'@

$response = Invoke-RestMethod `
  -Method Post `
  -Uri "https://overpass-api.de/api/interpreter" `
  -Headers @{ "User-Agent" = "DavelTrace/0.1 (your-email@example.com)" } `
  -Body @{ data = $query }

$response |
  ConvertTo-Json -Depth 20 |
  Set-Content "danang-pois.json" -Encoding UTF8
```

Thay `your-email@example.com` bằng email liên hệ thật. Kết quả được lưu trong file `danang-pois.json`.

## 4. Dữ liệu nhận được

Mỗi POI thường có cấu trúc tương tự:

```json
{
  "type": "node",
  "id": 123456789,
  "lat": 16.0678,
  "lon": 108.2208,
  "tags": {
    "name": "Nhà hàng mẫu",
    "amenity": "restaurant",
    "cuisine": "seafood",
    "opening_hours": "Mo-Su 09:00-22:00",
    "addr:street": "Bạch Đằng",
    "phone": "+84...",
    "website": "https://..."
  }
}
```

Các trường có thể thiếu vì dữ liệu OpenStreetMap do cộng đồng đóng góp. OSM thường không có rating, review, độ nổi tiếng hoặc thời gian tham quan trung bình.

## 5. Gợi ý lưu vào database

Các cột tối thiểu:

```text
osm_type
osm_id
name
category
subcategory
latitude
longitude
address
opening_hours
phone
website
raw_tags
source_updated_at
```

Dùng `(osm_type, osm_id)` làm khóa duy nhất để lần tải sau có thể cập nhật thay vì tạo bản ghi trùng.

## 6. Lưu ý sử dụng

- Ghi nguồn: `© OpenStreetMap contributors`.
- Dữ liệu OSM được phát hành theo giấy phép ODbL; nếu công khai database phái sinh thì cần kiểm tra nghĩa vụ attribution và share-alike.
- Không chạy nhiều tiến trình tải song song trên public Overpass.
- Nếu cần tải hoặc đồng bộ dữ liệu quy mô lớn, hãy tải file Vietnam `.osm.pbf` từ Geofabrik rồi lọc Đà Nẵng ở máy local.

Tài liệu tham khảo:

- Overpass API: <https://wiki.openstreetmap.org/wiki/Overpass_API>
- Chính sách Nominatim: <https://operations.osmfoundation.org/policies/nominatim/>
- Dữ liệu Vietnam từ Geofabrik: <https://download.geofabrik.de/asia/vietnam.html>
- Giấy phép OpenStreetMap: <https://osmfoundation.org/wiki/License/Licence_and_Legal_FAQ>
