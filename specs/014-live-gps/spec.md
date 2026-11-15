# Live GPS on the travel map

Created: 2026-11-15. Base: `feat/product-platform` at `ccb241d` (PR #19).
Branch: `codex/live-gps-tracking`.

## User scenarios

1. A traveler enables GPS on the map, grants foreground location permission, and
   sees the real position marker update whenever the device reports movement.
2. The camera follows by default. The traveler can pan freely while the marker
   keeps updating, then recenter and resume following without restarting GPS.
3. Stopping GPS, leaving the map, hiding the app or signing out releases the
   subscription. Returning resumes only a previously enabled tracking session.
4. Permission denial, disabled location services, unavailable fixes and unsupported
   devices show honest status without substituting route simulation coordinates.

## Requirements

- FR1: Start tracking only through the user's explicit GPS action; provide stop.
- FR2: Every valid newer fix updates the location marker in web and native maps.
- FR3: Follow camera must preserve user zoom on subsequent fixes; manual pan
  releases camera following, and recenter restores it.
- FR4: Maintain at most one position subscription. Reject invalid coordinates and
  out-of-order fixes; ignore callbacks after stop, suspension, provider change or dispose.
- FR5: Hidden tabs and app lifecycle suspension cancel the location stream;
  resume only if requested and visible. Foreground tracking is the supported scope.
- FR6: Map iframe reload/readiness must replay the latest state without putting
  personal coordinates in iframe URLs. Only the known parent/frame and origin
  may exchange location/gesture messages.
- FR7: Permission/service/provider failures clear stale live markers and expose a
  retry action. Device fixes must remain distinct from simulated route playback.
- FR8: Do not store, log or send the GPS stream to the backend. Retain existing
  route, search, playback and identity behavior. Add no dependency.

## Acceptance

Injected movement A -> B moves the marker without a second tap. Camera following,
manual pan/recenter, stop/restart, hidden-tab/background resume, permission/service
errors and late callbacks have focused tests. Existing Flutter suite, analyzer
and web build remain green. Browser checks use simulated coordinates and are
reported honestly; physical walking requires testing on the user's GPS device.
