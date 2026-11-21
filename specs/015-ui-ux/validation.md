# Validation — 2026-11-15

- Flutter analyzer: no issues.
- Full Flutter suite: 69 passed, including existing auth/recovery/offline/GPS/route tests.
- Final visual follow-up after chip contrast adjustment: all 9 UI/UX tests passed.
- Node map-location bridge: 4 passed.
- Release web build: passed; final color-only rebuild passed in 66.7s.
- Served-asset check: index.html, main.dart.js and both Vietnamese fonts return HTTP 200
  at port 5501, with SHA-256 digests equal to the final build files.
- `git diff --check`: clean. Secret sweep after staging: all 3 checks passed, including
  new tracked files and BE/.env exclusion.

## Visual review and corrections
Inspected rendered production widgets with bundled fonts at 390×844 and 320px with 200%
text, plus the desktop editor. Captures live in ignored FE/build/ui-review/:
account-390, trips-390, itinerary-390, planning-390, expenses-390,
account/expenses-320-large and -390-large, trip-editor-desktop.
Corrections from inspection: remove duplicate account heading, include real Vietnamese
font assets, use named places instead of planner IDs, and give selected-day/filter chips
dark text on pale backgrounds. The trip save action is explicitly tested above a 280px
keyboard inset. All subroutes remain within the 390px desktop frame.

Opened the actual release at http://127.0.0.1:5501 in the in-app browser with the existing
authenticated session. Verified trip collection -> selected trip/day view -> separate
planning screen -> back -> Account. The real account email and visible Sign out appeared;
no test plan was generated or accepted into that user's existing trip during inspection.
Automated fake-account tests cover sign out/session clearing and closing protected routes.

## Coverage limits
This change does not rerun a real Google consent/login handshake, send recovery email,
or verify physical GPS walking. Existing provider/GPS regressions pass, and no backend
provider configuration or GPS tracking logic changed. Native device/assistive-technology
usability should still be reviewed on hardware; screenshots and widget tests are not a
user study. The pre-existing catalog-only route eligibility is retained and explained.

## Final delivery
Convergence: implementation and required checks pass.
Implementation commit: 061af4b on fix/ui.
Ready PR: https://github.com/DangHung1110/Davel-Trace/pull/21
Base: feat/product-platform. No merge into the integration branch was performed.

## Map clarification follow-up
Following the zero-marker/GPS feedback, the empty map explains the missing itinerary
places and links directly to the schedule. A labeled Bật/Tắt GPS control replaces the
ambiguous icon; recenter is disabled before a valid fix. Route simulation controls are
hidden for zero stops. The map card scrolls within a bounded height so GPS stays accessible.
Two regressions cover GPS movement on an empty itinerary, enabled-state transitions,
the itinerary action, and a 320px viewport at 200% text. Full Flutter suite: 71 passed;
analyzer: no issues; Node map bridge: all 4 passed. Physical walking was not performed.
Release rebuild passed in 51.6s. In-app browser inspection verified that the real 3D map
loads, Bật GPS is visible, recenter is disabled before a fix, and the empty-state action
is reachable. No device permission was granted and no real coordinates were collected
during browser review. The movement regressions use injected test fixes.
