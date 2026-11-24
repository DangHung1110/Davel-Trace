# GPS and PMTiles on main

## Scope and acceptance

Integrate the map-loading and live GPS fixes from `fix/ui` onto a new branch based on `origin/main`. Keep the base theme, planner, catalog and datasets. The web debug map must load the local PMTiles with HTTP byte ranges. GPS on/off/on must restore the marker while stationary. Panning releases camera follow, and recenter restores it without remounting the map.

## Plan and analysis

- [x] Compare both sides from their merge base. The selected map commit has no path overlap with the three new main commits.
- [x] Apply `ff6df95` selectively. It fixes iframe remounting, adds a PMTiles range endpoint and includes unrelated visual changes to omit.
- [x] Port only the first-fix logic from the local GPS follow-up. Its result must not revive a stopped session or overwrite a stream fix.
- [x] Run Flutter, range, map bridge and live map smoke checks. Verify the final diff against main.

Saved-itinerary routing and the three-mode redesign belong to separate in-progress work. This transfer retains the existing routing contract and simulation controls. No dependency change is needed.

## Validation

- Flutter analyzer clean. All 84 Flutter tests passed, including stationary restart and stopped-session checks.
- Six JavaScript bridge tests and 46 focused backend tests passed, including PMTiles HTTP ranges, routing, CORS and snapshot v2 data gates.
- Chrome headless used the Flutter debug server and FastAPI PMTiles endpoint. Tiles rendered with zero console errors. With simulated positions, switching GPS off/on restored the marker without reloading the map.
- Planner sources, snapshot data and the shared theme match `origin/main` at `9e5843a`. Physical phone GPS and the PostgreSQL integration suite were outside this verification.
