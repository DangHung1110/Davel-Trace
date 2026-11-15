# Data + PATM + onboarding handoff

Updated: 2026-10-27  
Repository: `Davel-Trace`  
Branch: `feat/data-quality-integration`  
Branch checkpoint before this review: `852d873` — `docs: capture data and personalization handoff`

This note captures the current data/model state and the agreed next steps so a
new session can continue without reconstructing the full chat.

## Product context

Davel-Trace is a personalized Da Nang travel planner. Keep these data types
separate:

- **POI/weather data** describes a place (for example indoor, outdoor, both,
  rain protection, intensity, price, and activities).
- **User onboarding preferences** describe a person or travel group.
- **Human pair labels** compare the preferred visiting order of two POIs under
  a user/profile and context. They are not indoor/outdoor labels.

## Work completed and user decisions recorded

- User reviewed the weather label pages and supplied manual corrections/removal
  decisions. Examples: Nhất Lâm Thủy Trang Trà = outdoor; Queen Cobra is closed
  and should be removed; Dragon's Head and Pont main should be removed when they
  cannot be verified as real POIs; the actual Dragon Bridge POI = outdoor.
- Other confirmed weather decisions from the conversation: Vọc Glamping =
  outdoor activity; SAY Beer = indoor; Bạch Đằng walking street/night market =
  outdoor; Chợ Cồn and Khu Ẩm Thực Chợ Cồn = indoor.
- Snapshot documentation says 214 audited labels were retained and the current
  snapshot has no `space=unknown`. This does **not** prove the labels are all
  correct or that the independent blind-quality target has passed.
- A blind QA report cited earlier in chat was 29/40 = 72.5% (seed 777), after
  which systemic errors and labels were corrected. Treat 72.5% as a pre-final
  reference only; rerun a blind seed after all latest corrections before
  claiming final accuracy. Gold-standard macro-F1 target >=0.95 remains pending
  in `docs/weather-label.md`.
- Final PATM pair file was checked and versioned at
  `BE/ml/patm/pairs_v4_final.json`: 2,028 rows (944 rule, 934 LLM-judge, 150
  human), with 123 rows referencing removed POIs excluded. Current snapshot:
  742 POIs. The 150 human rows represent 150 distinct unordered comparisons:
  51 prefer-first, 57 prefer-second, 42 tie (108 decisive). Retire or explicitly
  revise the old target of 200 total comparisons. A new target of 150 decisive
  comparisons would require 42 additional decisive labels. Do not assume all
  50 vs the old target were lost POIs: the previous v4 card recorded 178 human
  rows, and the current filtered set has 150 (28 fewer).
- Added `BE/ml/patm/evaluate.py` and `BE/ml/patm/lpo_metrics.json` for a
  leave-POI-out evaluation on human-labeled comparisons. Seed 7: 1,302 pair
  rows in train, 1,020 decisive model rows after dropping 282 ties; held-out
  human subset 46 pairs (36 decisive, 10 ties). Model = 29/36 (80.6%); rule
  baseline = 21/36 (58.3%). No POI leakage. This is descriptive only: 36
  decisive labels is too small for a stable quality claim.
- Full pair-group PATM metrics in `BE/ml/patm/model_metrics.json`: CV 0.770,
  held-out 0.773 (n=335), flip consistency 0.776. These are mostly metrics
  against weak rule/LLM labels, not human satisfaction or trip-quality scores.
- Related checks passed: pair file format 0 errors; focused tests 49 passed,
  2 skipped. Commit `ab11e4f` is pushed to
  `feat/data-quality-integration`.

## Onboarding preference state

- Spec `specs/001-travel-agent-mvp/data-model.md` calls for five onboarding
  answers before the first recommendation: budget, pace, food preferences,
  fitness, and must-avoid. `User` also describes `party_type`, `trip_purpose`,
  `long_prefs`, and visited history.
- `BE/app/schemas/trip.py` has a partial `User` schema (`spending_level`,
  `pace`, `fitness`, `food_prefs`, `must_avoid`) but supplies defaults and lacks
  `outdoor_bias`. In the inspected repo, no user profile persistence/onboarding
  router or required five-answer gate was found. Therefore the schema/spec
  exist; the complete onboarding-to-planner flow does not.
- `BE/app/services/rank.py` accepts `user` and `ctx` dictionaries and can score
  budget, fitness, food preferences, activities, and context. However,
  `BE/app/routers/itinerary.py` currently calls it with only `{"budget": ...}`
  as the user object. PATM has user features (`pace`, `fitness`,
  `spending_level`, `outdoor_bias`) in `BE/ml/patm/features.py`.
- Important limitation: current PATM training rows are created with neutral
  user/context defaults (`train.py` calls `extract(a, b)`); the trained model
  has not learned conditional preference effects from the current pair file.
  `BE/ml/patm/judge_batch_v2.py` can generate profile-conditioned judge prompts,
  but a prompt generator is not completed labeled training data.

## Agreed next steps, in order

1. **Freeze the MVP preference contract.** Define a small set of options for
   budget, pace, effort/fitness, activity interests, food/diet, indoor/outdoor
   preference, and avoidances. Keep dietary/safety restrictions and explicit
   avoidances hard; treat taste/interest answers as weighted soft preferences.
   Do not enumerate every Cartesian combination. Use a few understandable
   archetypes plus independent option values/multi-selects.
2. **Run a small conditioned-data pilot and wire training together.** Start
   with 2–3 clearly distinct archetypes on a shared set of about 50 diverse
   POI pairs, so profile effects can be compared on the same pairs. This is a
   pipeline/signal pilot, not enough data for stable per-profile accuracy.
   Store the preference vector and context on each pair; pass both to
   `extract(a, b, user, ctx)` in training and evaluation. Keep genuine ties when
   the labeler sees no meaningful ordering; do not force directional labels to
   improve binary class balance. Prefer sampling pairs likely to show a
   meaningful profile distinction, and report the tie rate.
3. **Add the BE preference contract and wire it end to end.** Persist/accept the
   onboarding profile, merge it with trip-level overrides, and pass all
   relevant fields from `itinerary.py` into ranking/PATM. The `rank()` function
   signature already accepts user/context; current router wiring passes only
   budget. Keep rule-based fallback while the model is validated.
4. **Close the data gates.** Apply all latest weather audit changes, regenerate
   the final enriched snapshot, run consistency checks and a fresh blind QA
   seed. Retire the old 200-total-pair target; if the new baseline is 150
   decisive human comparisons, collect 42 more decisive labels (the current set
   has 108), without suppressing genuine ties.

## Constraints and clean handoff

- The preferred direction for the eventual FE merge was `Davel-Trace-002` as
  base, then port planner FE into it. FE merge/API integration has not been
  performed in this handoff.
- In the current working tree, `docs/mobile-ui-references.md` and
  `docs/research_brief_dynamic.md` are untracked user files. Leave them
  untouched and out of unrelated commits.
- Do not claim the PATM is personalized just because it has user feature
  columns. Training data and conditional evaluation must demonstrate that.
