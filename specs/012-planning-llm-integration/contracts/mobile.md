# Contract: Mobile Planning and AI Assistance

## Structured path

“Tạo phương án” remains available without AI and uses the owned trip/profile.

## Natural-language path

The optional prompt discloses external processing, requests interpretation, displays proposed fields/hard constraints/soft preferences/assumptions/unresolved values, permits correction, and submits only confirmed structured overrides. Interpretation never appears as saved or planned.

## Explanation path

Explanation is on-demand for a live persisted alternative. UI labels `ai_grounded` versus `deterministic` and retains gate/warning evidence during provider failure.

## Failure and layout

AI disabled/auth/quota/timeout/safety/malformed failures are distinct from planner failure. Structured planning stays enabled; offline cached plans stay readable. Controls remain accessible without horizontal overflow at 390×844, and no credential is shown.
