"""The one book of rules: every rule the planner knows, its layer and where it lives.

Layers (doc "Davel - Ham muc tieu v1"):
  physical  the trip cannot happen otherwise: opening hours, reachable legs, verified
            POIs. A constraint in CP-SAT and a hard gate check.
  user      the traveller said so: budget, return time, profile safety, must_visit /
            avoid (HCS), the lunch of a day that spans it. Constraint + hard check.
  taste     a rule of thumb. Under objective v1 it is a term of the objective (`term`)
            and the gate only reports it, unless the trip names it in `strict_rules`.
            `legacy_soft`: soft under the legacy objective too.
  quality   reported only, never fails a plan (F1, TIME_FIT, DINNER).
  edge      a legacy transition penalty on q_ij (soft_rules.edge_penalty /
            plan_penalties). Under objective v1 its `term` owns it and the edge
            penalty is not added (`edge_rules_active`).
  mirror    a gate check that re-runs other checks (TCS, HCS).

gate, soft_rules, objective and profiles read the sets below; none of them keeps its
own list. A rule's status history (active / deprecated, family, reason) stays in
`gate.RULE_FREEZE`.
"""

from __future__ import annotations

RULES: dict[str, dict] = {
    "FAR": {"layer": "physical"},
    "VROH": {"layer": "physical"},
    "B3": {"layer": "physical"},
    "PROFILE_SAFE": {"layer": "user"},
    "BCS": {"layer": "user"},
    "ETB": {"layer": "user"},
    "LUNCH": {"layer": "user", "term": "T5"},      # gate.check_lunch, inside HCS
    "A1": {"layer": "taste", "term": "T6"},
    "CAFE_CAP": {"layer": "taste", "term": "T3"},
    "CATEGORY_CAP": {"layer": "taste", "term": "T3", "legacy_soft": True},
    "NO_CONSECUTIVE": {"layer": "taste", "term": "T4", "legacy_soft": True},
    "NO_ADJACENT_FOOD": {"layer": "taste", "term": "T6"},
    "REST_FOLLOWS_LUNCH": {"layer": "taste", "term": "T7"},
    # T11 near-duplicates (objective.duplicate_counts). No gate check of their own:
    # a new CHECKS key would change the API's constraint_status keys; the eval
    # report counts them (reports/objective_v1/scripts/analyze_objective.py).
    "SAME_SITE": {"layer": "taste", "term": "T11"},
    "MARKET_REPEAT": {"layer": "taste", "term": "T11"},
    "SAME_DISH": {"layer": "taste", "term": "T11"},
    "F1": {"layer": "quality", "term": "T5"},
    "TIME_FIT": {"layer": "quality", "term": "T2"},
    "DINNER": {"layer": "quality", "term": "T5"},
    "A2": {"layer": "edge", "term": "T6"},
    "B1": {"layer": "edge", "term": "T4"},
    "B2": {"layer": "edge", "term": "T3"},
    "E2": {"layer": "edge", "term": "T2"},
    "TCS": {"layer": "mirror"},
    "HCS": {"layer": "mirror"},
}

# What HCS re-runs, in order. A taste rule is skipped while it is soft for the trip.
HCS_MIRROR = ("FAR", "PROFILE_SAFE", "VROH", "B3", "BCS", "ETB", "LUNCH",
              "A1", "CAFE_CAP", "NO_ADJACENT_FOOD", "REST_FOLLOWS_LUNCH",
              "CATEGORY_CAP", "NO_CONSECUTIVE")


def names(layer: str) -> frozenset[str]:
    return frozenset(name for name, rule in RULES.items() if rule["layer"] == layer)


def layer(name: str) -> str | None:
    return (RULES.get(name) or {}).get("layer")


def term(name: str) -> str | None:
    return (RULES.get(name) or {}).get("term")


QUALITY = names("quality")
TASTE = names("taste")
LEGACY_SOFT_TASTE = frozenset(n for n in TASTE if RULES[n].get("legacy_soft"))
EDGE = names("edge")
