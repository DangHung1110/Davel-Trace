# Pre-implementation analysis

FR1/4/5/7 -> G03/G05; FR2/3/6 -> G04/G05; FR8 -> G05/G06.
No blocking ambiguity: opt-in foreground tracking, marker always follows valid
fixes; camera follow is independent. Existing permissions and geolocator are reused.
Subscription generations and awaited cancellation protect late permission/fix
completion. Active-tab input is required because MainShell uses IndexedStack.
Web messages require both exact origin and exact frame source; location is queued
until MapLibre readiness and replayed after iframe reload. No GPS enters URLs.

Pre-implementation gate: ready. Final automated gates: 56 Flutter tests, 4 bridge
tests, 8 mobile GPS cases, analyzer and web release build pass; see validation.md.
Converged for the specified implementation scope. Real walking remains a device check.
