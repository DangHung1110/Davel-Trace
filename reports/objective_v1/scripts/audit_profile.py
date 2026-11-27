#!/usr/bin/env python3
"""One profile per request through POST /v1/itinerary on the 1-day scenarios of
BE/tools/audit_plans.py, with the solver's J, unit and status on every plan.

python audit_profile.py <code root> <profile> <weights.json|-> <out.json>

`weights.json`: a variant of objective_weights/v1.json (DAVEL_OBJECTIVE); "-" = the default.
J compares only between runs of one objective with the same unit (U): e.g. two candidate
caps, or two node orders. A run of another objective compares by its plans, not by J.
"""
import importlib.util
import json
import os
import sys
import time
from unittest import mock

root, profile, weights, out_path = sys.argv[1:5]
sys.path.insert(0, root)
os.chdir(root)
if weights != "-":
    os.environ["DAVEL_OBJECTIVE"] = weights
import warnings
warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402
from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services import profiles, trip_ctx  # noqa: E402

spec = importlib.util.spec_from_file_location("audit_plans", os.path.join(root, "BE", "tools", "audit_plans.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

_assemble = profiles._assemble


def _capture(acts, out, *args, **kwargs):
    plan = _assemble(acts, out, *args, **kwargs)
    plan["solver_objective"] = out.get("objective")
    plan["solver_status"] = out.get("status")
    plan["solver_unit"] = out.get("unit")
    return plan


profiles._assemble = _capture
snapshot = os.path.abspath(os.path.join("BE", "data", "snapshots", "danang-v2"))
settings = Settings(snapshot_dir=snapshot, snapshot_name="danang-v2")
client = TestClient(main_mod.app)
rows = []
with mock.patch.object(itinerary_mod, "get_settings", lambda: settings), \
        mock.patch.object(trip_ctx.weather_svc, "fetch_forecast", side_effect=RuntimeError("offline")):
    for key, extra in audit.SCENARIOS:
        trip = {**audit.DAY, **extra}
        if int(trip.get("days") or 1) != 1:
            continue
        t0 = time.perf_counter()
        body = client.post("/v1/itinerary", json={"trip": trip, "profiles": [profile]}).json()
        rows.append({"key": key, "wall_s": round(time.perf_counter() - t0, 3),
                     "plan": (body.get("plans") or [None])[0]})
json.dump({"profile": profile, "weights": weights, "rows": rows}, open(out_path, "w", encoding="utf-8"),
          ensure_ascii=False)
print(profile, weights, len(rows), "requests")
