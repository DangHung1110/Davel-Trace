"""Explanation builder (T042, lane C). Fact/inference-split reasons.

Per decision (POI pick / order): {claim, evidence[] (input/data refs),
inference (preference-based, stated), source, verified}. FR-023: every
decision has a reason. FR-024: fact vs inference split. FR-025/026:
unverified data gets an uncertainty flag, NEVER presented as fact.

Reuses reason strings from rank/context_score/retrieval outputs via
`from_ranked()` (their {reasons, fired} shapes plug in directly).
"""

from __future__ import annotations


def build_decision(claim: str, evidence: list[str] | None = None,
                   inference: str = "", source: str = "",
                   verified: bool = True) -> dict:
    """Normalize one decision; flag unverified (never a bare fact)."""
    evidence = list(evidence or [])
    uncertainty = [] if verified else ["chua xac minh — khong phai fact (FR-026)"]
    return {"claim": claim, "facts": evidence,
            "inference": inference or "",
            "inference_marked": bool(inference),
            "uncertainty": uncertainty, "source": source,
            "verified": verified}


def from_ranked(poi_id: str, name: str, ranked: dict,
                fired: list[dict] | None = None, verified: bool = True,
                source: str = "") -> dict:
    """Build a decision from rank/context_score output shapes."""
    evidence = [f"{name}: {r}" for r in ranked.get("reasons", [])]
    inference = "; ".join(f"{f.get('rule')}: {f.get('reason')}"
                          for f in (fired or []))
    if not inference and ranked.get("reasons"):
        inference = "uoc tinh tu preference (rank)"
    return build_decision(f"chon {name} ({poi_id})", evidence, inference,
                          source or "rank/context/retrieval", verified)


def validate_plan(explanations: list[dict]) -> list[str]:
    """Collectors of FR violations: reason-less or unflagged-unverified."""
    bad = []
    for i, e in enumerate(explanations):
        if not e.get("facts") and not e.get("inference_marked"):
            bad.append(f"decision {i} ({e.get('claim')}) thieu ly do (FR-023)")
        if not e.get("verified") and not e.get("uncertainty"):
            bad.append(f"decision {i} unverified khong gan co (FR-026)")
    return bad


def explain_plan(decisions: list[dict]) -> dict:
    """Wrap validated decisions: {"explanations", "violations"}."""
    return {"explanations": decisions, "violations": validate_plan(decisions)}
