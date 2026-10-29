# Mobile Demo Contract

## Screen and Navigation Contract

1. **Home/Planner**: source-status banner, current profile/trip summary, request plan action, and alternative cards.
2. **Itinerary**: active plan timeline, feasibility badge, cost/distance totals, accepted status, and open-map action.
3. **Map**: existing local Da Nang PMTiles canvas, stop markers, route status, location/search/route controls where available, and return-to-itinerary action.
4. **Expenses**: add expense, category list, budget/spent/remaining summary, and API/offline status.
5. **Profile**: traveler, pace, fitness, food/activity, avoid/accessibility, transport, API base URL, and reset-demo controls.

The primary bottom navigation exposes Itinerary, Map, Expenses, and Profile. Planning and alternative comparison may be an itinerary subflow so the compact bottom bar remains usable.

## Desktop Frame

- At viewport width above 600 logical pixels, center a 390×844 app surface with rounded corners and elevation.
- At width 600 or below, use the available width/height and remove desktop-only frame decoration.
- No horizontal overflow at either 390×844 or 1440×900.

## Live/Offline Honesty

- `Live`: health/planning call succeeded; acceptance identifier may be shown only after server confirmation.
- `Seeded demo`: bundled Da Nang alternatives and expenses; actions are local and explicitly labeled.
- `Stale`: previously successful data retained after a failed refresh; last data timestamp shown.

## Visual Direction

Use the existing Sơn Trà Breeze system: teal `#006A6A`, amber `#D97706`, white/slate surfaces, Material 3 rounded/pill cards, restrained color, readable Vietnamese typography, and one clear primary action per screen.

## Map Contract

The Flutter web map continues to load `web/data/danang.pmtiles` through `web/map_embed.html`. Route/location/search state must distinguish:

- local map loaded;
- online route available (OSRM or existing provider path);
- interpolated/demo route with warning;
- geolocation denied/unavailable.

## Test Keys

Stable widget keys are required for: source-status banner, request-plan button, alternative card, select/accept button, active-itinerary view, map tab, expenses tab, profile tab, and offline reset action.
