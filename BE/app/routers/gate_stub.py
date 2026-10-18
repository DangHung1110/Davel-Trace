"""Temporary lane-C mock for the lane-B seven-gate registry interface.

TODO(T033 wiring): replace these mock checks with
``BE.app.services.gate.CHECKS``/``all_pass`` when lane-B services are
available in this branch. Keep the interface unchanged; do not copy gate
logic here.
"""

from __future__ import annotations


def _mock_result() -> dict:
    return {"passed": True, "score": 1.0}


def check_far(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    return _mock_result()


def check_vroh(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    return _mock_result()


def check_b3(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    return _mock_result()


def check_bcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    return _mock_result()


def check_etb(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    return _mock_result()


def check_tcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    return _mock_result()


def check_hcs(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    return _mock_result()


CHECKS = (("FAR", check_far), ("VROH", check_vroh), ("B3", check_b3),
          ("BCS", check_bcs), ("ETB", check_etb), ("TCS", check_tcs),
          ("HCS", check_hcs))


def all_pass(itinerary: dict, trip: dict, pois: dict, matrix: dict) -> dict:
    failed = [name for name, check in CHECKS
              if not check(itinerary, trip, pois, matrix)["passed"]]
    return {"passed": not failed, "failed": failed}
