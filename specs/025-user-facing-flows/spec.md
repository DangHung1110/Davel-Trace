# User-facing mobile flows

Travelers need to create an account, start a trip, and make decisions about a
schedule without interpreting service names, scoring badges, or support logs.
Use the existing Davel Trace visual system with fewer competing actions.

## Acceptance

- Sign-in shows email, Google, and clear routes to registration, password
  recovery, and the sample trip. Google consent is requested on its own step.
- Registration validates inputs and explains email verification. Account
  recovery, device sign-out, account export, and deletion remain reachable.
- A traveler can save a profile with a name. Pace, fitness, and preferences are
  grouped so a first-time traveler can choose whether to fill them in.
- Planning makes the next action and the status of the schedule clear. Travelers
  can review AI-parsed wishes, compare schedules, preview a route before accepting
  it, and reuse saved schedules.
- The map puts the route, distance, stops, and GPS state first. A route preview
  communicates when the line only shows the order of the stops.
- Expenses show budget, spending, and remaining funds. A single row menu groups
  editing and deletion. Storage notices appear when they affect the traveler.

## Plan and checks

Keep existing repositories and API contracts. Refine shared headers, screen
content, and the transitions between existing steps. Verify the main and error
states with Flutter widgets at mobile widths and enlarged text. Verify tiles,
route rendering, and location bridge events in the browser preview.
