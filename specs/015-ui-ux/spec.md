# 015 — Clear mobile journeys

## Problem and outcome
Travelers confuse login identity with travel preferences, cannot readily find sign out,
and must scroll past planning tools before seeing their itinerary. Creation sheets and
account pages also escape the mobile frame on desktop.

## User journeys
- P1: Open Account to see the signed-in email, security and a visible sign-out action.
  Travel preferences must never be presented as authentication identity.
- P1: Open Trips, select a trip, then see its dates and daily itinerary first. Enter a
  separate planning workspace to generate, review and explicitly accept alternatives.
- P1: Create/edit a trip with clearly grouped dates, people, budget, transport and daily
  hours. Editing must preserve existing values rather than silently resetting hours.
- P2: Find travel preferences in the planning context; distinguish account-wide defaults
  from a trip's saved snapshot. Keep archive/restore/delete under trip management.
- P2: Map and expenses identify the selected trip; empty states direct users to Trips.

## Acceptance
- Account is accessible even when no travel profile exists. Sign out clears the session
  through the existing AuthController and returns to sign in, including from subpages.
- Trip cards select the same trip whose itinerary, expenses and map are displayed.
- Planning never accepts an alternative implicitly; demo and server persistence are
  described honestly in user language, without database/framework jargon.
- 320px and 390px widths, a short viewport, keyboard insets and enlarged text remain
  usable. All routes/dialogs share the same constrained desktop mobile surface.
- Preserve Google login, recovery, offline sync, manual activities, expenses and live GPS.
- No new runtime dependencies, authentication contracts or scheduling algorithms.

## Map clarity follow-up
An empty trip must explain why there are no itinerary markers and offer a direct return
to add places. GPS remains usable without stops. Its opt-in control must say Bật/Tắt GPS;
recenter is disabled until a valid fix arrives. Simulated route playback is shown only
when itinerary stops exist, and must never stand in for real movement. No traveled-path
recording, background tracking or automatic itinerary generation is introduced.
