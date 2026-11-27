#!/usr/bin/env python3
"""BE/tools/audit_plans.py with the solver's J and status written on every plan.

python audit_capture.py <code root> <audit_plans.py args...>
e.g.  python audit_capture.py <archive> --only T,W,M,D,E --out cap.json --flags cap_flags.json

Adds `solver_objective` (CP-SAT objective, 1000 x U units) and `solver_status` (optimal /
feasible-timeout) to each plan of the saved responses. Run it from a `git archive` copy;
nothing here changes the plans. J compares only inside one model: two runs of the same
values and candidates that differ in the search (node order, budget, hint).
"""
import os
import runpy
import sys

root = sys.argv[1]
sys.path.insert(0, root)
os.chdir(root)
from BE.app.services import profiles  # noqa: E402

_assemble = profiles._assemble


def _with_objective(acts, out, *args, **kwargs):
    plan = _assemble(acts, out, *args, **kwargs)
    plan["solver_objective"] = out.get("objective")
    plan["solver_status"] = out.get("status")
    return plan


profiles._assemble = _with_objective
sys.argv = [os.path.join(root, "BE", "tools", "audit_plans.py")] + sys.argv[2:]
runpy.run_path(sys.argv[0], run_name="__main__")
