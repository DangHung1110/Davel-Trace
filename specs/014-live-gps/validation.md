# Validation — live foreground GPS (2026-11-15)

- Based on `feat/product-platform` at PR #19 merge `ccb241d`, not main/dev.
- Entire Flutter suite: **56 passed**, 10 seconds. Existing auth, map, route
  play/pause/reset, planning, expenses and offline behavior remain covered.
- Focused GPS/mobile rerun: **8 passed** at 390×844. Covers movement A -> B,
  following camera, manual pan/recenter, panning before the first fix, invalid and
  out-of-order positions, errors, rapid start/stop, hidden tabs, background resume,
  provider replacement, dispose and geolocator OS-stream cancellation.
- Embedded MapLibre bridge: **4 Node tests passed** using the production inline
  script with stubbed MapLibre/DOM. Verifies readiness queuing/latest fix,
  subsequent marker movement without resetting zoom, pan/recenter, clearing,
  exact origin/parent checks and rejection of invalid coordinates.
- Flutter analyzer: **No issues found**, 6.1 seconds.
- Web release build: passed, 60.6 seconds, including the web iframe implementation.
- No dependency or lockfile change; existing foreground platform permissions reused.
- Local frontend and backend readiness returned HTTP 200; the served map HTML
  hash matches the new GPS source exactly.
- No GPS persistence, backend transmission, location URL parameter or production
  GPS log was introduced. Temporary state traces used during debugging were removed.

Widget tests explicitly wait for stream cancellation's event-loop completion.
Native tile requests are stubbed by Flutter tests (HTTP 400 diagnostics expected);
their filesystem cache port is stubbed to ignored build output. Automated movement
is injected and does not represent a real walking test or physical GPS accuracy.

Convergence: implementation/automated acceptance gates passed for the specified
foreground scope. Physical movement on the user's device remains a manual check.
