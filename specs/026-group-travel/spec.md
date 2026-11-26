# Group travel

Families and friends need a shared trip where everyone can contribute and the
leader can make one clear decision. Members should be able to operate the trip
without sharing private profiles or GPS histories.

## User journeys

1. A leader starts a group trip or shares an existing trip, creates a revocable
   invitation, and can manage members and guests. An account needs a valid
   invitation to join. Group size for planning includes travelers without
   accounts.
2. A member picks a catalog place or submits a preference and can vote on
   suggestions. The leader can add a contribution for a guest and confirms
   which conditions apply to everyone. Selection of a place is structured.
   Optional interpretation of free text extracts the person's wishes from that
   text only.
3. The leader runs one planner for the whole group. Members see the resulting
   alternatives, can vote and discuss, and can view the shared route. Only the
   leader can confirm. A published itinerary remains active while a new round is
   discussed. Group chat records when proposals are ready and when a plan is
   confirmed.
4. Group chat lets people coordinate and share a meeting place. A leader may
   request a location fix when choosing a new starting point. The leader
   confirms the catalog place, time and progress before the app replans the
   remaining activities. A personal GPS marker stays local.
5. A shared expense records a payer and an explicit set of participants. Shares
   sum to the cost in whole đồng. Reimbursements change balances independently
   of spending. People outside the group cannot read its finances.
6. Group members can record contributions to a common fund. Group leaders can
   spend from funds already contributed and record the amount, purpose and
   beneficiaries. Personal advances and reimbursements keep their own balances.
   Demo payments are marked as simulated and do not move real money.

Trip creation saves dates, headcount and estimated budget. Planning reuses those
values. The AI entry accepts additional wishes and opens a review of what the
text changes. A group leader changes shared trip details in group settings.
Offer the group fund from the expense tab and the group workspace.

## Verification

Verify permissions in the API with leader, member and unrelated accounts.
Exercise invitation lifecycle, tenant isolation, votes, planning round changes,
catalog resolution, location opt-in, expense reconciliation and rendering at
mobile size and enlarged text. Rerun the existing personal planning, map,
expense, authentication and offline tests. No new package dependency.
