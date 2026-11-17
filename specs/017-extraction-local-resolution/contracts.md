# Additive API contract — 017

`POST /v1/trips/{trip_id}/ai/interpretations` still accepts `{text: string}` and
requires the current owner. Existing response keys and statuses are preserved.
`hard_constraints.must_visit/avoid` contain only uniquely resolved verified IDs.

New response example:

```json
{
  "place_resolutions": [
    {
      "constraint": "must_visit",
      "name": "cà phê An",
      "status": "ambiguous",
      "candidates": [
        {"poi_id": "an-1", "name": "Cà phê An", "type": "cafe", "lat": 16.1, "lon": 108.1, "address": ""},
        {"poi_id": "an-2", "name": "Cà phê An", "type": "cafe", "lat": 16.2, "lon": 108.2, "address": ""}
      ]
    },
    {"constraint": "avoid", "name": "địa điểm chưa có", "status": "not_found", "candidates": []}
  ]
}
```

Candidates are backend-derived and never forwarded to the model. Every reference is
kept separate by constraint. Exact normalized matches take precedence over partial
matches; duplicate exact names still require selection. Unmentioned model-generated
names are returned as unresolved and never added to hard constraints.

New Flutter accepts absent place_resolutions as an empty list. On review, each pending
reference requires a candidate choice or explicit removal. Confirming sends the existing
`constraint_overrides` format with must_visit/avoid IDs only; resolution metadata and
raw names never enter planner input. Contradictory IDs cannot be confirmed. Cancelling
review does not create a planning request. No new endpoint or database column.
