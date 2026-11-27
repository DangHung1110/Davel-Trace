# Interactive planning latency

Use the current planner and catalog in the app. Present options as soon as the
planning request completes, with catalog names available at first render.

- Keep the existing objectives, constraints and hard gate. Bound the initial
  search and diversity refills for the interactive planning request.
- Keep the existing direct solver and replan search budgets. The interactive
  budget can return fewer certified options when it exhausts its search.
- Keep planning-readiness diagnostics off the app's rendering path.
- Compare cold and warm 1-day and 2-day product requests, inspect solver time
  separately from lifecycle persistence, and verify gate status and place names.

## Local verification

FastAPI TestClient called the product planning endpoint on `danang-v2` with
the real optimizer, a fixture identity and isolated SQLite persistence. The
same 1-day trip, 07:00–21:00 for two travelers, took 57.10 s cold and 47.35 s
warm on the merged code before the interactive budget. The solver occupied
56.99 s and 47.28 s. The obsolete readiness request added 26 ms and 8 ms.

With the interactive budget, the same request took 16.78 s cold and 13.85 s
warm. The 2-day variant took 23.24 s. Each request returned three alternatives
that passed the hard gate and included names for every stop. These are local
API timings for representative requests. Flutter coverage verifies that the
result is published without an additional readiness request.
