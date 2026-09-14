# Davel Trace Mobile

Flutter mobile prototype for the core travel experience:

- itinerary creation and a sample day plan;
- an interactive Da Nang map with route and place markers;
- trip budget and expense tracking.

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

Android and iOS currently use the OpenStreetMap raster fallback. Native PMTiles
integration will be handled in a dedicated follow-up milestone.
