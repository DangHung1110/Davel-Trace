# Davel Trace Mobile

Flutter mobile prototype for the core travel experience:

- selectable mock itinerary creation (date, duration, origin, and interests);
- an interactive Da Nang map with an OSRM road route and moving car demo;
- in-memory trip budget and expense creation/removal.

All demo itinerary and expense changes are kept in widget memory only and reset
when the app is refreshed.

## Run locally

Install the Flutter stable SDK, then run:

```powershell
flutter pub get
flutter run
```

On Flutter Web, the map screen renders the bundled Da Nang vector archive at
`web/data/danang.pmtiles` with MapLibre and 3D buildings. It does not require a
VietMap API key. The PMTiles archive is loaded into the browser once per page
session so Flutter's development server does not need HTTP range support.

The mock place coordinates are sent from Flutter to the embedded map. The map
requests a road-following geometry from the public OSRM demo server, then draws
the route and animates the car along it. A straight-line fallback is shown when
the OSRM demo server is unavailable.

Android and iOS currently use the OpenStreetMap raster fallback. Native PMTiles
integration will be handled in a dedicated follow-up milestone.
