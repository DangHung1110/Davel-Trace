# Trip planning inputs

Travelers can search the catalog for accommodation, select or remove a hotel on the planning screen, and select indoors, outdoors or balanced in the trip editor. Hotel selection survives reopening the trip and contributes its catalog ID to every fresh planning request, including requests confirmed through AI. Without a hotel, planning can continue.

The trip saves the selected outdoor preference as `preference_overrides.outdoor_bias`. Verify the phone-size flow and the fitness slider with Flutter analyzer and tests.

## Plan and checklist

- [x] Confirm that the catalog supports filtering by `lodging` and the planner accepts `constraint_overrides.base_poi_id`.
- [x] Reuse the trip's preference map and preserve unrelated saved keys. Catalog lodging entries are bases and need not be marked as verified activity stops.
- [x] Wire accommodation search, trip editor, online and cached trip projections, and planner requests.
- [x] Verify select, clear, repeated planning, the trip payload and the fitness slider. No new dependencies.

The catalog query must filter before pagination. Existing plan requests already use trip version and constraints for retries, so a changed hotel cannot reuse the previous request key. Replanning can fall back to the hotel saved in the trip until there is a more recent completed stop.

## Validation

Flutter analyzer reported no issues. All 88 Flutter tests passed, including profile creation with a selected fitness level, the trip preference payload, and hotel selection, reopening, AI confirmation and removal. All 50 focused backend tests passed. Both real catalog snapshots returned 76 lodging entries through the filtered endpoint.
