# Flutter Profile and Trip Contract

## Root states

```text
loading -> needs_profile | ready | demo | recoverable_error
needs_profile -> saving_profile -> ready | conflict | validation_error
ready -> trip_list(empty|loaded) -> trip_detail
ready -> editing_profile | editing_trip | editing_activity
ready -> lifecycle_confirmation | conflict | recoverable_error
```

Authenticated and demo modes use different repositories and visible labels. A live network failure never switches to demo data.

## Repository boundaries

- `ProfileRepository`: read, save, reset; accepts expected version/idempotency intent.
- `TripRepository`: list/detail/create/update, active selection, lifecycle, days, activity CRUD/reorder.
- A temporary management adapter projects the active durable trip into existing map/expense/planning consumers.
- Access credentials remain managed by the shared identity-aware `ApiClient`; per-request headers carry idempotency keys.

## Conflict and failure behavior

- Editors preserve entered values after validation, network, and version-conflict failures.
- `VERSION_CONFLICT` shows “Dữ liệu đã thay đổi trên thiết bị khác” with Reload and Review/Reapply choices; never auto-overwrite.
- Date reduction lists affected dates/activities before a confirmed retry.
- Failed live writes never appear as persisted success.
- Archiving/deleting the active trip clears the context; the UI does not select another trip silently.

## Screens

- Profile onboarding and review/editor with visible hard versus soft values.
- Trip list with search, lifecycle filters, deterministic sort, active marker, and empty state.
- Trip create/edit with effective-profile review and hard-constraint feedback.
- Trip detail with day selector and ordered activity timeline.
- Activity editor/status/reorder controls and overlap warning.
- Archive, restore, deletion, recovery, and conflict confirmations.

Keep existing shell/navigation keys. The current itinerary tab becomes the trip workspace while map, expense, and planning receive a compatibility projection.

## Mobile quality

- Every primary flow uses scrollable safe-area/keyboard-aware layout at 390×844 and text scale 200%.
- Primary touch targets are at least 48 logical pixels; dense fixed action rows become wraps, menus, or full-width actions.
- Multi-field rows stack when width/text scale requires.
- Status is conveyed by text/icon, not color alone.
- Custom/unresolved activities without coordinates are omitted from route geometry with an honest explanation.

## Test obligations

- Controller: singleton profile, active uniqueness, lifecycle, conflict draft preservation, failed network without demo fallback.
- Repository: auth/idempotency/version headers, filters, stable error mapping, day/activity contracts.
- Widget: onboarding, trip create/reopen, multi-day selection, activity actions, archive/restore/delete/recover, conflict dialog, 200% scale.
- Compatibility: current navigation keys, phone frame, map, expense/profile, demo/live/stale labels remain reachable.
