# Preview the itinerary route

Travelers can open a map from each planning option before saving it. The map shows the option's ordered catalog stops and uses the existing road routing service. Leaving the preview returns to the same option. The saved map and foreground GPS remain accessible from the trip.

- The saved map and its route follow the day selected in the itinerary.
- The saved planner version remains visible in the itinerary and on its map after reopening a trip, even when the manual activity list is empty.
- The draft and saved maps display a dashed connection when the catalog has coordinates but the routing provider returns no road geometry. The label identifies it as illustrative or a matrix estimate.
- The draft route API verifies trip ownership, takes catalog POI IDs in planner order, and performs no itinerary writes.
- Demo plans use the local sample catalog, including when the saved itinerary is empty.

Verify the empty-trip preview from the planner, identity of the saved itinerary before and after preview, route order in the contract, foreign trip rejection and existing GPS behavior.
