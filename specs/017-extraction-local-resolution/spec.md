# 017 — Extract wishes, resolve places locally

## Why
Travelers submit short natural-language wishes, but interpretation currently sends
catalog names to the hosted model. Extraction must have a catalog-independent input
size and must not ask AI to identify authoritative place records.

## User stories and acceptance
1. A traveler describes party size, budget, times, preferences and places to visit or
   avoid. AI returns only extracted slots and names explicitly mentioned, never IDs,
   routes, prices or opening hours. Neither catalog names nor candidates are sent to AI.
2. The backend resolves extracted names using verified local catalog records. Matching
   ignores accents, case, punctuation and repeated whitespace. A unique exact match
   wins over partial matches; multiple exact matches remain ambiguous. Unknown or
   unverified places never silently become hard constraints.
3. Before planning, the traveler reviews all values. Ambiguous names show named local
   candidates with distinguishing location information and no preselected choice.
   Unknown names show that they were not found. Each pending place must be selected
   or explicitly removed before confirmation; cancelling creates no planning request.
4. Only confirmed catalog IDs reach the existing deterministic planner. Soft interests
   such as “thích biển” do not become must-visit places. AI errors leave form planning
   usable. Existing ownership, secret handling and feasibility gates remain effective.

## Scope
Product interpretation API and Flutter confirmation, with an additive response field.
No new dependencies, migrations, provider calls during automated tests, planner tuning,
UI redesign, or changes to legacy parser/test-harness routes. Existing explanation and
shadow capabilities remain separate optional operations.

## Success checks
The same traveler text/context produces exactly the same external prompt with an
empty or a 750-place catalog. An ambiguous must-visit and avoid choice reaches planner
input only after review. Unknown/unverified candidates cannot be selected. Existing
clients can still read the existing fields; new clients accept older responses.
