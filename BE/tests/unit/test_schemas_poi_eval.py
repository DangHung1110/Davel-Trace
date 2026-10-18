"""Unit test for POI/eval schemas (T007-poi+eval). Stdlib runner + pydantic.

Run from repo root: python BE/tests/unit/test_schemas_poi_eval.py -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import ValidationError  # noqa: E402

from BE.app.schemas.eval import EvaluationRecord  # noqa: E402
from BE.app.schemas.poi import POI, Restaurant  # noqa: E402

SNAPSHOT = os.path.join("data", "snapshots", "danang-v1", "pois.json")


class TestSchemasPoiEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SNAPSHOT, encoding="utf-8") as f:
            cls.seed = {p["poi_id"]: p for p in json.load(f)["pois"]}

    def test_seed_pois_validate(self):
        for pid, raw in self.seed.items():
            kw = {k: v for k, v in raw.items() if k in POI.model_fields}
            POI(**kw)
        print(f"\n seed POIs validate: {len(self.seed)}/{len(self.seed)}")

    def test_restaurant_extends_poi(self):
        raw = dict(self.seed["mi-quang-ba-mua"])
        kw = {k: v for k, v in raw.items() if k in Restaurant.model_fields}
        kw.setdefault("cuisine", ["Mì Quảng"])
        kw.setdefault("meal_slots", ["lunch"])
        r = Restaurant(**kw)
        self.assertEqual(r.poi_id, "mi-quang-ba-mua")
        self.assertEqual(r.visit_min.p50, 72)

    def test_missing_required_field_errors(self):
        raw = {k: v for k, v in self.seed["son-tra"].items()
               if k in POI.model_fields}
        del raw["visit_min"]
        with self.assertRaises(ValidationError):
            POI(**raw)

    def test_bad_visit_ordering_errors(self):
        raw = {k: v for k, v in self.seed["son-tra"].items()
               if k in POI.model_fields}
        raw["visit_min"] = {"p25": 100, "p50": 50, "p75": 30}
        with self.assertRaises(ValidationError):
            POI(**raw)

    def test_t022_context_fields(self):
        raw = {k: v for k, v in self.seed["my-khe"].items()
               if k in POI.model_fields}
        for k in ("ambience", "crowd", "dietary", "pros", "cons"):
            raw.pop(k, None)
        p = POI(**raw, ambience="thoáng đãng", crowd="vừa phải",
                dietary=["hải sản"], pros=["hoàng hôn"], cons=["nắng gắt"])
        self.assertEqual(p.crowd, "vừa phải")
        self.assertEqual(p.dietary, ["hải sản"])
        self.assertEqual(p.pros, ["hoàng hôn"])

    def test_backward_compat_old_seed(self):
        raw = {k: v for k, v in self.seed["son-tra"].items()
               if k in POI.model_fields}
        self.assertNotIn("crowd", raw)
        self.assertNotIn("dietary", raw)
        p = POI(**raw)  # old seed without new fields still validates
        self.assertEqual(p.crowd, "")
        self.assertEqual(p.dietary, [])

    def test_evaluation_record_defaults(self):
        rec = EvaluationRecord(itinerary_id="it1", baseline="distance-only",
                               gate={"passed": True, "violations": []})
        self.assertIsNone(rec.pairwise_label)
        self.assertEqual(rec.soft, {})


if __name__ == "__main__":
    unittest.main()
