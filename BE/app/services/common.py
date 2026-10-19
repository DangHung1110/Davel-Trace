"""Lane-B service helper names -> BE/common.py (T061c consolidation).

The implementations (to_min/hh/in_range/parse_hours/total_fee/status_map)
used to be copy-pasted here and in eval/metrics.py. T061c keeps ONE
implementation in `BE/common.py`; this module re-exports the names lane-B
services (gate, validator, optimizer, profiles, response, replan) import,
so their call sites are untouched.

ponytail: `hh` is the historical lane-B name for `hhmm`; re-exported as an
alias. New code should import from `BE.common` directly.
"""

from __future__ import annotations

from BE.common import (  # noqa: F401  (re-exported seam)
    deadline,
    hh,
    hhmm,
    in_range,
    parse_hours,
    plan_cost,
    status_map,
    to_min,
    total_fee,
)

__all__ = [
    "to_min", "hh", "hhmm", "in_range", "parse_hours",
    "total_fee", "plan_cost", "deadline", "status_map",
]
