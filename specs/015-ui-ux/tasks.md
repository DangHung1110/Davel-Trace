# Tasks and checklist

- [x] T001 Audit screen semantics and repository/API boundaries; record design and contracts.
- [x] T002 Analyze requirements: every journey has an owning screen/API and validation plan.
- [x] T003 Unify mobile frame and add real Account screen; keep sign out reachable.
- [x] T004 Separate trip collection, daily itinerary, planning and travel preferences.
- [x] T005 Rebuild trip editor; preserve time values; align shared controls and empty states.
- [x] T006 Test navigation, payloads, responsive layouts and regressions; inspect screenshots.
- [x] T007 Converge documentation, commit, push and open PR into product-platform (#21).
- [x] T008 Map follow-up: label GPS, explain zero stops, link to itinerary and verify
  live movement/follow/recenter still work with an empty trip; build and update PR #21.

Follow-up analysis gate: existing GPS stream and map bridge already update location;
the missing elements are discoverable controls and a useful empty state. No new API,
dependency or sensor behavior required. Validate with the existing movement tests and
an empty-map action/layout regression. Actual device walking remains a manual check.

Analysis gate: PASS. Existing APIs cover scope; no dependency or migration required.
No implementation started before this gate. Remaining limitations must be recorded in validation.
