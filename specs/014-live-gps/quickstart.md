# Try live GPS

The feature branch is `codex/live-gps-tracking`, based on
`feat/product-platform` merge `ccb241d`. It does not change main/dev or backend env.

## On the current local web app

1. Open http://127.0.0.1:5501 and hard reload (Ctrl+F5) after the new build.
2. Sign in or choose the existing demo entry, then open **Bản đồ**.
3. Tap the labeled **Bật GPS** button (tooltip **Bật GPS trực tiếp**) and allow location access in
   the browser/OS. No location request is made before this action.
4. A blue marker represents device location. As the device reports movement,
   its marker updates automatically. The high-accuracy stream requests a 2 m
   movement filter; Android requests about one update per second. Actual delivery
   rate and accuracy depend on the sensor/OS, not a timer or route simulation.
5. Drag/zoom the map to browse freely. The blue marker continues moving, but the
   camera stops following. **Về vị trí của tôi** recenters and resumes follow.
6. Tap **Tắt GPS trực tiếp** to stop and remove the live marker. Switching away
   from the map or backgrounding the app cancels the subscription. Returning
   resumes only if tracking was enabled before suspension.

A newly created trip saves its dates/budget but does not automatically add places.
For itinerary markers: open the trip -> **Lập lịch cho chuyến đi** -> generate and
explicitly choose a plan, or add a catalog place manually. When the map has no stops,
**Thêm điểm vào lịch** opens that itinerary. GPS is independent of those stops and
works on an empty map. **Về vị trí của tôi** is disabled until a fix arrives.
Current GPS shows a moving position marker and camera follow; it does not draw or
save a traveled-path history.

The car/play/pause controls remain route simulation, separate from the blue GPS
marker. This feature does not provide turn-by-turn navigation or route recalculation.
Permission/service errors clear the live marker and allow retry using the same button.
Coordinates are not persisted, included in iframe URLs, logged or sent to the backend.

## On a phone

Prefer the native Android/iOS app for a physical walking test. The existing
foreground location permissions are reused; no background permission is added.
You can use demo mode to exercise GPS without depending on a backend login.

For a browser on a phone use trusted HTTPS. A LAN URL such as
`http://192.168.x.x:5501` does not normally qualify for web geolocation; localhost
is the local-development exception. Laptop location may be coarse Wi-Fi/IP
position rather than a phone's GPS. The accuracy estimate is displayed when given.

The web map's local PMTiles cover Da Nang. Outside that footprint the real marker
still reports device coordinates, but the local basemap may have no coverage.
No real walking/Android/iOS hardware test is claimed by automated validation.

## Reproduce checks

From `FE`:

```powershell
& '..\.flutter-sdk\bin\flutter.bat' analyze --no-pub
& '..\.flutter-sdk\bin\flutter.bat' test --no-pub
node --test tool/map_location_bridge.test.cjs
& '..\.flutter-sdk\bin\flutter.bat' build web --release --no-pub --no-wasm-dry-run --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
```

Serve the result with the repository byte-range server (only one server on 5501):

```powershell
Push-Location build/web
python ../../../server.py --port 5501
Pop-Location
```

Sources checked:
- https://pub.dev/packages/geolocator
- https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/watchPosition
- https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/clearWatch
