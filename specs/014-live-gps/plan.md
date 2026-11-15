# Plan

Use the checked-in Spec Kit sequence/templates; command skills are absent from
this checkout. The checkpoint was clean, and the new branch was pushed before work.

- Extend existing MapLocationProvider with an injectable watch stream using the
  installed geolocator 14.1.1, high accuracy and a small movement distance filter.
  Keep currentLocation compatibility. Include optional accuracy and fix timestamp.
- MapScreen owns subscription, cancellation generation, desired tracking state,
  follow state, app lifecycle observer and active-tab input from MainShell.
- Native FlutterMap updates the marker independently of camera recenter requests;
  manual gestures disable follow. Existing route simulation remains independent.
- Web wrapper sends state via origin/source-checked postMessage, replays it on
  iframe load, and releases listeners on dispose. The embedded MapLibre map queues
  location until ready, updates the marker, follows only when requested and reports
  manual pan to Flutter. It does not acquire another GPS watch inside the iframe.
- Existing foreground Android/iOS permissions suffice. No background permission,
  service, telemetry endpoint or additional package is introduced.

Tests cover stream lifecycle/races, marker/camera behavior, visible status, iframe
messaging and route-playback regression. Use an isolated headless browser with
mocked location fixes where practical; do not claim a real walking test.

References checked: geolocator package docs and MDN watchPosition/clearWatch.
Web location requires HTTPS or localhost and explicit browser permission. On a
phone, ordinary LAN HTTP is not a secure context; use a native app or trusted HTTPS.
