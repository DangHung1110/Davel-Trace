# Validation — 2026-11-17

## Design and behavior review
Read 16 source screens in Stitch project 11832778903374325952; inspected eight core
HTML designs and trip/map screenshots. Applied a softer mint/slate coastal theme,
tonal navigation, local code-drawn coastal illustration and consistent shared cards,
headers and forms. Kept four real destinations and existing data/confirmation rules;
did not add the reference's fictitious subscriptions, bookings, 2FA, weather or ratings.

Removed competing controls by using one play/pause action, an expense action menu,
collapsed expense filters/account-deletion recovery/history options, and lighter
secondary planning links. Filter/edit/delete regression verifies all remain usable.

Rendered actual Flutter screenshots to ignored FE/build/ui-review using existing
CAPTURE_UI tests. Inspected trips, itinerary, expenses, account, planning and 320px
large-text states. Corrected clipped header text by stacking the secondary action
and hiding redundant branding at narrow widths/large text. Final UI checks pass.

## GPS and actual map failure
Two independent issues addressed: identity-based stop-list comparison could reload
the iframe/reset route state during rebuilds; real Chromium then exposed the Flutter
debug asset server returning **200, 10,996,060 bytes** for a one-byte Range request.
PMTiles reported `Server returned no content-length header or content-length exceeding
request`. MapLibre load/style/tiles-ready flags alone were insufficient to detect it.

Stable bridge compares serialized route values, caches current route/location until
MapLibre readiness and updates in place. Public read-only backend endpoint uses the
existing Starlette FileResponse to return proper byte ranges and browser ETag headers.
Configured iframe probes that endpoint and falls back to the packaged static asset
for range-capable hosting. Failed initial tile loading remains an error, not ready.
GPS outside known Da Nang bounds does not move the local camera to a blank region.

Real headless Chromium smoke: base tiles and style loaded, no console errors; 30
synthetic fixes update marker to 16.06029/108.22 with the same map instance and zero
load resets. A synthetic Hanoi fix leaves the camera unchanged. Screenshot:
FE/build/ui-review/map-browser-390.png. The test uses an isolated browser profile,
closes its own processes, does not enable device GPS and does not control user tabs.

## Checks
- Full Flutter suite: **83 passed**, 19s execution; final analyzer **no issues**, 3.1s.
- Final header adjustment: **9 UI tests passed** with regenerated previews, 10s.
- Backend map byte-range/CORS/missing-file plus routing/health/config suite:
  **14 passed**, 18.47s. Includes actual archive bytes, 416, preflight and path secrecy.
- JavaScript bridge VM: **6 passed**. Tests readiness/error, outside coverage,
  latest pending fixes, camera release/recenter and invalid source/origin rejection.
- Real Chromium smoke: **passed**, styleLoaded/tilesLoaded true, zero map errors.
- API connectivity from actual app origin: health 200; protected planning with a
  deliberately invalid synthetic token returns readable 401, proving CORS/preflight
  and transport. No real account/trip was read or changed for this check.
- Running backend `/v1/health` and `/v1/ready`: 200; archive range 0-15: 206, 16 bytes.
- Debug-only Flutter demo on port 5501. No release web build, dependencies, lockfile,
  database migrations, secrets or archive data changed. git diff --check passes.

The screenshot supplied during work showed a network error while backend was being
restarted and separate chrome-extension:// console errors. Connectivity is verified
after restart; no extension settings were changed. Network failure text is now plain
traveler-facing language, preserving NETWORK_ERROR classification and correlation IDs.

## Convergence
Converged. Main 916886f retained PR #23. fix/ui checkpoint
6fdff78 was pushed before implementation; seven earlier uncommitted changes remain
in named stash and are already integrated by #23. They were not reapplied over the
new local-extraction pipeline. Map commit ff6df95, UI commit 847f355 and validation
144ac62 are pushed on fix/ui. Open PR #24 targets main, as explicitly requested earlier
by the owner: https://github.com/DangHung1110/Davel-Trace/pull/24
No automatic merge, direct main/dev push, force push or remote branch deletion.
