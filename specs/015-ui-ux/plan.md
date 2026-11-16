# Plan

Baseline: product-platform 2df1755 (GPS PR #20 merged). Work branch: fix/ui.
The tree was clean, so the baseline branch was pushed without an empty checkpoint commit.
Spec Kit command wrappers are unavailable; its spec/plan/checklist/tasks/analyze sequence
is recorded in these source documents before implementation.

## Design review
Applied Anthropic frontend-design SKILL.md (official anthropics/skills repository),
downloaded through skill-installer to ignored FE/build/ui-skills for this session.
It is a session-local reference, not a globally installed skill or application dependency.

Audience: Vietnamese travelers preparing and following a Da Nang trip on a phone.
Retain the existing coastal teal identity. Bundle Be Vietnam Pro regular/semibold
from google/fonts with OFL license: the prior fontFamily declaration had no font assets.
Tokens: sea #006A6A, deep sea #005050, ink #0F172A, slate #475569,
canvas #F8FAFC, white #FFFFFF. Use amber only for warnings/budget states.
Type: 24/18/16/14/12, clear headings, readable labels, no decorative uppercase labels.
Layout: left aligned; 16px page gutters, 24px section gaps, 12px field gaps;
48px minimum primary controls. Quiet bordered sections instead of repeated shadows.

```
Trips                    Trip detail            Account
title + Create           back / trip title       identity + email
selected trip            dates / people          security
all trip cards           Plan / Preferences      travel preferences (link)
archive (secondary)      day selector             sign out
                         daily activities
```

The first draft retained an always-expanded planning panel; rejected because it hides
the main daily itinerary. Planning gets its own workspace with one primary action.
Creation uses a full route with a stable save action, rather than a cramped sheet.

## Contracts to preserve
Account -> AuthController/account, /v1/account/me and existing session/recovery APIs.
Travel preferences -> AppState profile methods, /v1/profile (not identity editing).
Trips -> AppState create/select/update/archive/restore/delete, /v1/trips.
Activities/expenses -> existing management repository for the selected trip.
Planning -> existing planning repository, explicit request/review/accept, optional Gemini.
No UI control may silently substitute profile defaults for saved trip values.

Audit fixes within the same UI journey: expense persistence labels use management
storage/sync rather than the planner's last result; accepting/reactivating reloads trip
detail; trip selection/edit clears prior alternatives and ignores late planner responses.
Demo alternatives are previews with disabled server actions. Existing routing only uses
linked catalog places; manual-activity copy now makes that boundary explicit.

## Verification
Widget navigation/account/logout and trip form payload tests; layout checks at narrow,
short and enlarged-text viewports; existing full Flutter regression suite; analyzer;
release web build and actual rendered screenshots of key journeys; map bridge Node tests.
