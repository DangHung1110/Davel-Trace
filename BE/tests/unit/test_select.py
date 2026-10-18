"""Unit tests for the T033 select/gate interface seam."""

import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.routers import gate_stub, select as select_mod  # noqa: E402


class TestGateStub(unittest.TestCase):
    def test_registry_matches_seven_gate_interface(self):
        self.assertEqual(
            [name for name, _ in gate_stub.CHECKS],
            ["FAR", "VROH", "B3", "BCS", "ETB", "TCS", "HCS"],
        )
        args = ({}, {}, {}, {})
        for _, check in gate_stub.CHECKS:
            self.assertEqual(check(*args), {"passed": True, "score": 1.0})
        self.assertEqual(gate_stub.all_pass(*args),
                         {"passed": True, "failed": []})

    def test_all_pass_reports_mocked_failed_gate(self):
        pass_check = Mock(return_value={"passed": True, "score": 1.0})
        fail_check = Mock(return_value={"passed": False, "score": 0.0})
        with patch.object(gate_stub, "CHECKS",
                          (("FAR", pass_check), ("BCS", fail_check))):
            result = gate_stub.all_pass("i", "t", "p", "m")

        self.assertEqual(result, {"passed": False, "failed": ["BCS"]})
        for check in (pass_check, fail_check):
            check.assert_called_once_with("i", "t", "p", "m")


class TestSelectGateWiring(unittest.TestCase):
    def setUp(self):
        select_mod.reset_store()

    def tearDown(self):
        select_mod.reset_store()

    def test_select_passes_stored_gate_context_to_registry(self):
        plan = {
            "itinerary_id": "it-1",
            "itinerary": {"activities": [{"poi_id": "p1"}]},
            "trip": {"budget": 100},
            "pois": {"p1": {"verified": True}},
            "matrix": {},
        }
        select_mod.register([plan])
        report = {"passed": True, "failed": []}
        with patch.object(gate_stub, "all_pass", return_value=report) as check:
            result = select_mod.select(select_mod.SelectIn(itinerary_id="it-1"))

        check.assert_called_once_with(plan["itinerary"], plan["trip"],
                                      plan["pois"], plan["matrix"])
        self.assertEqual(result, {"active_id": "it-1"})
        self.assertEqual(select_mod.get_store()["selected"], "it-1")


if __name__ == "__main__":
    unittest.main()
