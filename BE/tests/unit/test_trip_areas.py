"""Trip areas: the zones a traveller wants the plan to stay in.

- `TripRequest.areas` takes the danang-v2 `zone` codes;
- the parser reads them from the request text ("trung tâm", "Mỹ Khê", "Hội An"...);
- the app passes `ConstraintOverrides.areas` through the trip snapshot, or saves
  the zones on the trip (`preference_overrides.areas`) for every plan and replan;
- retrieval drops every other zone ("ngoai khu vuc"), never a must_visit, and
  changes nothing when no area is given.

Run: python -m pytest BE/tests/unit/test_trip_areas.py -q
"""

import os
import sys
import unittest
from datetime import date, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import ValidationError  # noqa: E402

from BE.app.modules.planning_lifecycle.api import ConstraintOverrides  # noqa: E402
from BE.app.modules.planning_lifecycle.service import _trip_request  # noqa: E402
from BE.app.modules.trips.domain import validate_trip  # noqa: E402
from BE.app.schemas.trip import AREA_CODES, TripRequest  # noqa: E402
from BE.app.services.parser import areas_in_text, parse  # noqa: E402
from BE.app.services.profiles import _activity_warnings  # noqa: E402
from BE.app.services.retrieval import activity_requirements, in_areas, retrieve  # noqa: E402
from BE.ml.data.v2_rules import ZONES  # noqa: E402


class TestSchema(unittest.TestCase):
    def test_the_codes_are_the_snapshot_zones(self):
        self.assertEqual(set(AREA_CODES), set(ZONES))

    def test_no_area_by_default(self):
        self.assertEqual(TripRequest().areas, [])
        self.assertEqual(TripRequest(areas=None).areas, [])

    def test_a_repeated_area_counts_once(self):
        trip = TripRequest(areas=["hoi_an", "trung_tam", "hoi_an"])
        self.assertEqual(trip.areas, ["hoi_an", "trung_tam"])

    def test_an_unknown_area_is_refused(self):
        with self.assertRaises(ValidationError):
            TripRequest(areas=["Hội An"])


class TestAreasInText(unittest.TestCase):
    def test_each_way_of_naming_a_zone(self):
        for text, code in (
            ("ưu tiên check-in trung tâm", "trung_tam"),
            ("ở quận Hải Châu", "trung_tam"),
            ("tắm biển Mỹ Khê", "son_tra_my_khe"),
            ("lên bán đảo Sơn Trà", "son_tra_my_khe"),
            ("leo Ngũ Hành Sơn", "ngu_hanh_son"),
            ("làng đá Non Nước", "ngu_hanh_son"),
            ("dạo phố cổ Hội An", "hoi_an"),
            ("đi Bà Nà Hills", "ba_na_tay"),
            ("qua đèo Hải Vân", "hai_van_lien_chieu"),
            ("biển Liên Chiểu", "hai_van_lien_chieu"),
        ):
            self.assertEqual(areas_in_text(text), [code], text)

    def test_the_city_is_not_an_area(self):
        self.assertEqual(areas_in_text("lịch Đà Nẵng 1 ngày: biển và hải sản, ngân sách 1 triệu"), [])
        self.assertEqual(areas_in_text(""), [])
        self.assertEqual(areas_in_text(None), [])

    def test_gold_q14(self):
        text = "đi Đà Nẵng từ 07:00 đến 18:00 1 triệu, ưu tiên check-in trung tâm"
        self.assertEqual(areas_in_text(text), ["trung_tam"])

    def test_several_zones_in_the_order_named(self):
        self.assertEqual(areas_in_text("sáng tắm biển Mỹ Khê, chiều đi Hội An rồi về Mỹ Khê"),
                         ["son_tra_my_khe", "hoi_an"])

    def test_a_mall_is_not_the_centre(self):
        self.assertEqual(areas_in_text("đi trung tâm thương mại"), [])
        self.assertEqual(areas_in_text("trung tâm mua sắm, rồi dạo trung tâm"), ["trung_tam"])

    def test_the_centre_of_hoi_an_is_hoi_an(self):
        self.assertEqual(areas_in_text("dạo trung tâm Hội An"), ["hoi_an"])
        self.assertEqual(areas_in_text("trung tâm phố cổ"), ["hoi_an"])

    def test_a_zone_the_traveller_refuses(self):
        self.assertEqual(areas_in_text("ở trung tâm, không đi Hội An"), ["trung_tam"])
        self.assertEqual(areas_in_text("ở trung tâm không muốn đi Hội An"), ["trung_tam"])
        self.assertEqual(areas_in_text("tránh Sơn Trà, thích Ngũ Hành Sơn"), ["ngu_hanh_son"])
        self.assertEqual(areas_in_text("khong di hoi an"), [])

    def test_a_negation_in_another_clause_does_not_count(self):
        self.assertEqual(areas_in_text("không thích đông người, ở Hội An"), ["hoi_an"])

    def test_typed_without_accents(self):
        self.assertEqual(areas_in_text("di hoi an va ba na"), ["hoi_an", "ba_na_tay"])
        self.assertEqual(areas_in_text("TRUNG TAM"), ["trung_tam"])

    def test_other_accents_are_another_word(self):
        # "hai vạn" (twenty thousand) and "tranh" (a painting) only fold like a zone or a no.
        self.assertEqual(areas_in_text("vé hai vạn"), [])
        self.assertEqual(areas_in_text("xem tranh ở Hội An"), ["hoi_an"])
        self.assertEqual(areas_in_text("đi bộ phố cổ"), ["hoi_an"])


FULL = {"city": "Đà Nẵng", "date": "2026-11-28", "start_time": "07:00", "end_time": "18:00",
        "days": 1, "travelers": 2, "budget": 1000000, "transport": ["motorbike"],
        "must_visit": [], "avoid": [], "activities": [], "food_prefs": [], "order_prefs": [],
        "hard_constraints": [], "soft_prefs": [], "uncertainties": []}


def mock(slots):
    return lambda prompt, schema: dict(slots)


class TestParse(unittest.TestCase):
    def test_parse_fills_areas_from_the_text(self):
        out = parse("đi Đà Nẵng 1 triệu, ưu tiên check-in trung tâm", llm_fn=mock(FULL))
        self.assertEqual(out["trip"].areas, ["trung_tam"])

    def test_no_area_named_no_area(self):
        out = parse("đi Đà Nẵng 1 triệu", llm_fn=mock(FULL))
        self.assertEqual(out["trip"].areas, [])

    def test_the_model_cannot_add_an_area(self):
        out = parse("đi Đà Nẵng 1 triệu", llm_fn=mock(dict(FULL, areas=["trung_tam"])))
        self.assertEqual(out["trip"].areas, [])


def poi(pid, zone, cat="restaurant", **extra):
    return {"poi_id": pid, "zone": zone, "cat": cat, "fee": 0, "verified": True,
            "plan_tier": "main", "opening_hours": ["06:00-22:00"], **extra}


POIS = [
    poi("centre_food", "trung_tam"),
    poi("centre_cafe", "trung_tam", "cafe"),
    poi("hoian_food", "hoi_an"),
    poi("hoian_museum", "hoi_an", "museum", name="Bảo tàng Hội An"),
    poi("beach", "son_tra_my_khe", "beach", name="Bãi biển Mỹ Khê"),
    poi("no_zone", None),
    poi("hoian_draft", "hoi_an", verified=False),
    poi("centre_draft", "trung_tam", verified=False),
]
TRIP = {"budget": 1000000, "start_time": "07:00", "end_time": "18:00",
        "must_visit": [], "avoid": [], "activities": []}


def ids(result, key):
    return sorted(r["poi_id"] for r in result[key])


class TestRetrieval(unittest.TestCase):
    def test_other_zones_are_left_out(self):
        out = retrieve(dict(TRIP, areas=["trung_tam"]), POIS)
        self.assertEqual(ids(out, "candidates"), ["centre_cafe", "centre_food", "no_zone"])
        reasons = {e["poi_id"]: e["reason"] for e in out["excluded"]}
        for pid in ("hoian_food", "hoian_museum", "beach", "hoian_draft"):
            self.assertEqual(reasons[pid], "ngoai khu vuc")

    def test_several_zones(self):
        out = retrieve(dict(TRIP, areas=["trung_tam", "son_tra_my_khe"]), POIS)
        self.assertEqual(ids(out, "candidates"), ["beach", "centre_cafe", "centre_food", "no_zone"])

    def test_a_must_visit_elsewhere_is_kept(self):
        out = retrieve(dict(TRIP, areas=["trung_tam"], must_visit=["hoian_museum"]), POIS)
        self.assertIn("hoian_museum", ids(out, "candidates"))
        self.assertNotIn("hoian_food", ids(out, "candidates"))

    def test_only_places_inside_wait_for_verification(self):
        out = retrieve(dict(TRIP, areas=["trung_tam"]), POIS)
        self.assertEqual(ids(out, "needs_verification"), ["centre_draft"])

    def test_no_area_changes_nothing(self):
        before = retrieve(TRIP, POIS)
        for areas in ([], None):
            self.assertEqual(retrieve(dict(TRIP, areas=areas), POIS), before)
        self.assertNotIn("ngoai khu vuc", str(before["excluded"]))

    def test_a_poi_without_a_zone_is_kept(self):
        self.assertTrue(in_areas({"poi_id": "x"}, {"hoi_an"}))
        self.assertTrue(in_areas({"poi_id": "x", "zone": "hoi_an"}, set()))
        self.assertFalse(in_areas({"poi_id": "x", "zone": "hoi_an"}, {"trung_tam"}))

    def test_the_local_tier_opens_for_what_the_zone_lacks(self):
        # Three known pagodas elsewhere do not serve a "chùa" wish in the centre.
        pagodas = [poi(f"hoian_pagoda{i}", "hoi_an", "temple", name=f"Chùa {i}") for i in range(3)]
        local = poi("centre_pagoda", "trung_tam", "temple", name="Chùa Phổ Đà", plan_tier="local")
        trip = dict(TRIP, activities=["chùa"])
        self.assertNotIn("centre_pagoda", ids(retrieve(trip, pagodas + [local]), "candidates"))
        out = retrieve(dict(trip, areas=["trung_tam"]), pagodas + [local])
        self.assertEqual(ids(out, "candidates"), ["centre_pagoda"])


class TestWishReport(unittest.TestCase):
    def test_a_wish_only_another_zone_meets(self):
        pool = [p for p in POIS if p["zone"] == "trung_tam" and p["verified"]]
        outside = [p for p in POIS if p["zone"] not in (None, "trung_tam") and p["verified"]]
        _groups, report = activity_requirements(["tắm biển"], pool, [], [], outside=outside)
        self.assertEqual(report[0]["status"], "outside_areas")
        self.assertIn("khu vuc da chon", _activity_warnings(report)[0])

    def test_without_areas_it_is_still_missing_data(self):
        _groups, report = activity_requirements(["tắm biển"], [POIS[0]], [], [])
        self.assertEqual(report[0]["status"], "no_verified_poi")


SNAPSHOT = {"id": "t1", "start_date": "2026-11-28", "day_start": "07:00:00",
            "day_end": "18:00:00", "traveler_count": 2, "indicative_budget": 1000000,
            "preferred_transport": "motorbike", "profile_snapshot": {},
            "preference_overrides": {}}


class TestAppContract(unittest.TestCase):
    def test_the_app_may_send_areas(self):
        self.assertEqual(ConstraintOverrides(areas=["trung_tam"]).areas, ["trung_tam"])

    def test_an_unknown_area_is_refused(self):
        with self.assertRaises(ValidationError):
            ConstraintOverrides(areas=["downtown"])
        with self.assertRaises(ValidationError):
            ConstraintOverrides(areas=list(AREA_CODES) + ["trung_tam"])

    def test_no_areas_leaves_the_overrides_as_they_were(self):
        # The overrides are part of the idempotency fingerprint.
        self.assertNotIn("areas", ConstraintOverrides().model_dump(exclude_none=True))

    def test_the_areas_reach_the_planner(self):
        trip = _trip_request({**SNAPSHOT, "areas": ["hoi_an", "ba_na_tay"]}, {})
        self.assertEqual(trip["areas"], ["hoi_an", "ba_na_tay"])

    def test_no_areas_plans_anywhere(self):
        self.assertEqual(_trip_request(SNAPSHOT, {})["areas"], [])

    def test_the_areas_saved_on_the_trip_reach_the_planner(self):
        saved = {**SNAPSHOT, "preference_overrides": {"areas": ["son_tra_my_khe"],
                                                      "base_poi_id": "hotel"}}
        self.assertEqual(_trip_request(saved, {})["areas"], ["son_tra_my_khe"])

    def test_a_replan_keeps_the_saved_areas(self):
        saved = {**SNAPSHOT, "preference_overrides": {"areas": ["hoi_an"]}}
        replan = {"remaining_from": "13:00", "completed_poi_ids": ["p1"],
                  "current_poi_id": "p1"}
        self.assertEqual(_trip_request(saved, replan)["areas"], ["hoi_an"])

    def test_the_request_areas_win_for_that_request(self):
        saved = {**SNAPSHOT, "preference_overrides": {"areas": ["hoi_an"]}}
        self.assertEqual(_trip_request({**saved, "areas": ["trung_tam"]}, {})["areas"],
                         ["trung_tam"])
        # [] is an AI proposal that names no zone: the trip's own stay in force.
        self.assertEqual(_trip_request({**saved, "areas": []}, {})["areas"], ["hoi_an"])

    def test_saved_values_that_are_not_codes_are_skipped(self):
        for saved, expected in ((["Hội An", "trung_tam"], ["trung_tam"]),
                                ("trung_tam", []), (None, []), ({"x": 1}, []),
                                ([["hoi_an"]], [])):
            snapshot = {**SNAPSHOT, "preference_overrides": {"areas": saved}}
            self.assertEqual(_trip_request(snapshot, {})["areas"], expected, saved)


TRIP_FORM = {"title": "Đà Nẵng", "start_date": date(2026, 11, 28),
             "end_date": date(2026, 11, 28), "traveler_count": 2,
             "day_start": time(7), "day_end": time(18)}


class TestSavedOnTheTrip(unittest.TestCase):
    def test_the_trip_saves_zone_codes(self):
        for areas in ([], ["trung_tam"], list(AREA_CODES), None):
            validate_trip({**TRIP_FORM, "preference_overrides": {
                "areas": areas, "base_poi_id": "hotel"}})
        validate_trip({**TRIP_FORM, "preference_overrides": {"outdoor_bias": 0.5}})

    def test_a_label_or_a_lone_code_is_refused(self):
        for areas in (["Trung tâm"], "trung_tam", [None], ["trung_tam", "downtown"]):
            with self.assertRaises(ValueError, msg=repr(areas)):
                validate_trip({**TRIP_FORM, "preference_overrides": {"areas": areas}})


if __name__ == "__main__":
    unittest.main()
