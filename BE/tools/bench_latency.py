"""POST /v1/itinerary latency on a snapshot: median, p95, max (Phase 2 gate: p95 < 8 s).

Runs the real pipeline in-process with the 3 default plans per request, so it
measures planning and not the network. Weather is mocked offline: a slow
forecast API would otherwise count as planner latency. Run it on the deploy
machine: the earlier numbers come from a 12-core laptop.

Usage (repo root):
  python BE/tools/bench_latency.py --snapshot BE/data/snapshots/danang-v1 [--rounds 3]

Exits 1 when a plan fails or p95 misses the gate.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GATE_P95_S = 8.0
BASE = {"start_time": "08:00", "end_time": "20:00", "budget": 3000000, "days": 1}
COUPLE = {"party_type": "couple", "pace": 2, "fitness": 2}
FAMILY = {"party_type": "family", "pace": 1, "fitness": 1}
SCENARIOS = (
    {},
    {"profile": COUPLE},
    {"profile": FAMILY},
    {"profile": COUPLE, "activities": ["tắm biển"]},
    {"profile": FAMILY, "activities": ["bảo tàng"]},
    {"profile": COUPLE, "activities": ["chùa"], "budget": 600000},
    {"activities": ["tắm biển", "hải sản"]},
)


def summarize(seconds: list[float]) -> dict:
    """Median, nearest-rank p95 and max of the request times."""
    ordered = sorted(seconds)
    rank = max(0, round(0.95 * len(ordered)) - 1)
    return {"requests": len(ordered), "median_s": round(statistics.median(ordered), 2),
            "p95_s": round(ordered[rank], 2), "max_s": round(ordered[-1], 2)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args(argv)

    from fastapi.testclient import TestClient

    from BE.app import main as main_mod
    from BE.app.config import Settings
    from BE.app.routers import itinerary as itinerary_mod
    from BE.app.services import trip_ctx

    snapshot = os.path.abspath(args.snapshot)
    settings = Settings(snapshot_dir=snapshot, snapshot_name=os.path.basename(snapshot))
    client = TestClient(main_mod.app)
    seconds, failed = [], 0
    with mock.patch.object(itinerary_mod, "get_settings", lambda: settings), \
            mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                              side_effect=RuntimeError("offline")):
        for _ in range(args.rounds):
            for scenario in SCENARIOS:
                started = time.perf_counter()
                response = client.post("/v1/itinerary", json={"trip": {**BASE, **scenario}})
                seconds.append(time.perf_counter() - started)
                plans = response.json().get("plans") if response.status_code == 200 else None
                failed += not plans or not all(plan.get("passed") for plan in plans)
    report = summarize(seconds)
    ok = not failed and report["p95_s"] < GATE_P95_S
    print(f"{report} failed={failed} cores={os.cpu_count()} "
          f"gate p95<{GATE_P95_S:g}s: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
