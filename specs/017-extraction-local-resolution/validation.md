# Validation and convergence — 2026-11-17

## Automated checks

- Backend boundary/catalog/AI gateway/Groq/secrets/API/lifecycle/real stable solver:
  **50 passed in 78.50s**. Isolated test databases and fake completions/transports;
  no live hosted-provider requests or personal traveler data sent during these tests.
- Flutter analyzer: **no issues**, 78.8s on this checkout.
- Full Flutter suite: **79 passed**, 15s test execution after analysis. Includes seven
  new model/review widget cases and two AppState cases: no default selection, visit and
  avoid choices, explicit removal, not-found handling, cancellation, contradictory IDs,
  legacy response parsing and IDs-only planner overrides. Existing map/GPS/playback,
  trip/expense/profile/auth/offline/planning tests stay green.
- A focused review-widget run exposed a selected-dropdown height overflow. The selected
  item now uses one line, with distinguishing location information below the field and
  in candidate choices. Final full-suite results above include this correction.
- `git diff --check`: passed. No dependency, lockfile, migration, key or AGENTS.md change.

## Prompt measurement (characters, not token billing)

Compared origin/main 384f575 and task service using an injected fake completer, the
same text `Đi Đà Nẵng 2 người, ngân sách 3 triệu, thích biển`, empty trip context and
the real 750-place catalog. Baseline pre-schema prompt: **14,085 characters**; task:
**770 characters** (94.5% less). JSON output schema is unchanged and added separately
by the gateway. Task prompt is byte-for-byte identical with an empty catalog.
No actual provider token usage or monetary saving is claimed.

## Running demo

- Backend runs from this task worktree, retaining ignored local configuration and
  existing PostgreSQL data. `/v1/health` and `/v1/ready` return 200; schema 013_001
  and catalog ready. Optional OSRM reports degraded, as on the existing demo.
- Flutter is `flutter run -d chrome` debug on port 5501, in a separate background
  process. No release build was made for this task. Confirmed the Dart debug service,
  app startup log, HTTP 200, and the rendered mobile sign-in screen on Chrome.
- Authenticated ambiguity/confirmation is exercised by API/widget/state tests; no
  real account was created or signed in through the browser for verification.
- `server.py --port 5502` from this task worktree returns **206**, Content-Range
  `bytes 0-15/10996060`, and exactly 16 PMTiles bytes. Port 5500 belonged to an earlier
  server that timed out, so the range check used this separate task server.
- Original fix/ui workspace and its seven uncommitted files remain unchanged.

## Convergence review

Implementation PASS: every story maps to backend and mobile checks. LLM input is
catalog-independent; verified local candidates are authoritative; unknown/ambiguous
names cannot silently enter planner input. The solver and planning endpoint contract
are unchanged. Matching intentionally uses exact normalized or whole-word substring
names/available aliases, not fuzzy spelling correction; unknown names remain reviewable.

Converged. Backend commit 9b520f1 and mobile commit 250b8d2 are pushed on
fix/llm-extraction-catalog. The owner explicitly requested targeting main instead
of the usual dev branch. Open, non-draft PR #23 targets main:
https://github.com/DangHung1110/Davel-Trace/pull/23

GitHub connector could not create the PR (403, integration lacks permission); used
the existing Git credential helper with the GitHub REST API, keeping credentials
in memory and out of output/files. No PR into dev was created. No direct push to
main/dev, merge, force-push or remote branch deletion was performed.
