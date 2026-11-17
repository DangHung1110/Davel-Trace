# 018 — Softer coastal mobile UI and stable GPS map

## Intent
Refresh the Flutter mobile app from the owner's Stitch project
https://stitch.google.com/projects/11832778903374325952, adapting its coastal cards,
clear headings and comfortable spacing to existing functionality. The owner requests
lighter colors, fewer competing buttons and repair of the map when GPS is enabled.

## Stories and acceptance
- Travelers see a consistent, gentle coastal visual language across authentication,
  trips, itinerary/planning, map, expenses, preferences and account/security screens.
  Existing fields, source labels and actions remain available. No fabricated weather,
  booking, ratings, live progress or AI functionality from decorative reference data.
- Each main screen has a clear primary action. Rare/secondary actions are grouped or
  disclosed where relevant; do not duplicate create/play/map actions in the same area.
  Trip details open before planning. Four destinations remain trips/map/expenses/account.
- Phone layouts work at 390x844 and at 320px with larger text and the keyboard. Form
  validation and confirmation, offline/AI/permission error states remain readable.
- GPS fixes update the user marker without reloading the embedded web map, fetching
  the same archive again or resetting route playback/camera. Equivalent stops received
  as a new list do not count as a route change. Actual route changes update in place.
- A location outside the local Da Nang archive is described honestly, rather than
  leaving a blank map or implying national coverage. Users can return to the trip.
- Map load failure shows an actionable retry; its status is distinct from GPS status.
  Location permission is requested only after the user's GPS action; no fake fixes.

## Scope
Lane C Flutter/screens/theme, web map bridge and serving the existing PMTiles archive
through the backend with HTTP byte-range support. No planner/backend business changes,
new dependencies, release web builds or changes to tracked PMTiles. Keep existing
demo/live/confirmation behavior from main and the extraction/local-resolution feature.
