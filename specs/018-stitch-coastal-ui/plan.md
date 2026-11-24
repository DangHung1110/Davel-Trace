# Plan — 018

Work on fix/ui as requested. Base main 916886f includes PR #23. Preserve seven prior
uncommitted changes in named stash (also integrated by #23); do not reapply old catalog
shortlisting over the new extraction boundary. Checkpoint 6fdff78 pushed before work.

Spec Kit wrappers are unavailable here; record equivalent specify/clarify/plan/checklist/
tasks/analyze/implement/converge artifacts. Resolved decisions: adapt, not copy, the
Stitch layouts; soften saturated teal/coral; retain four real app destinations. Existing
user instruction to target main persists for delivery; no direct push or automatic merge.

Read all 16 Stitch screen titles and download eight core HTML references plus trip/map
screenshots through the Stitch connector. Use pale mint/slate surfaces, restrained teal
actions, tonal navigation, rounded cards and small editorial labels. Build a lightweight
code-drawn coastal motif with Flutter painting, avoiding remote photo dependencies.
Apply the shared theme to every form/account subpage, then adapt primary screen layouts.
Use one primary action, popup/expansion for secondary controls, without deleting flows.

GPS investigation: MainShell reconstructs stop lists; web MapCanvas compares list identity
and assigns iframe.src on route updates. Introduce value-based route payload comparison
and a stable iframe with readiness handshake; send setRoute only for real changes.
Extract a pure bridge-state helper for regression tests and keep source/origin checks.
Map JS retains latest route/location before readiness, reports map ready/error to parent,
supports retry and handles zero/one stop. Distinguish a fix outside PMTiles bounds;
keep the local map view usable and provide return-to-trip. Native map still uses its
existing provider; test location/playback and no invented native PMTiles support.

Checks: reproduce bridge lifecycle failure, JS VM tests, Flutter widget/state tests,
all Flutter tests, analyzer and local debug HTTP/PMTiles checks. Review UI at phone
sizes and inspect screenshots without leaving a persistent computer-control session.
No schema/dependency/secret changes. Commit small steps, push fix/ui and PR to main.

Real Chromium smoke found a second concrete failure: the Flutter debug asset server
returns the archive without suitable byte serving. MapLibre can report load/style
success even when PMTiles tiles fail. Add a fixed public read-only archive endpoint
using existing Starlette FileResponse (range support verified in installed 0.48.0),
with CORS range/ETag headers. Pass configured API origin into the iframe; prefer that
archive if its one-byte range probe succeeds, otherwise use the packaged static asset.
Standalone server.py keeps its current local path. Add range/CORS/missing-file tests;
the browser smoke must assert zero console errors and loaded archive tiles, not merely
the map load event. This scope refinement is necessary to repair the requested GPS map.
