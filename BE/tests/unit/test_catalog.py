import json
from pathlib import Path

import pytest

from BE.app.modules.catalog.application import get_place, search
from BE.app.modules.catalog.domain import normalize_text, public_place, search_places, valid_place
from BE.app.modules.catalog.infrastructure import _load_path, _snapshot_path
from BE.app.services.retrieval import load_pois_json

V1_SNAPSHOT = Path("BE/data/snapshots/danang-v1/pois.json")
V2_SNAPSHOT = Path("BE/data/snapshots/danang-v2/pois.json")


def _place(identifier, name, verified, **extra):
    return {
        "poi_id": identifier, "name": name, "type": "Điểm tham quan",
        "cat": "landmark", "lat": 16.0, "lon": 108.2,
        "verified": verified, "source": "fixture", "fetched_at": "2026-10-03",
        **extra,
    }


def test_search_is_diacritic_insensitive_stable_and_verified_first():
    rows = [_place("b", "Cầu Rồng", False), _place("z", "Cầu Rồng", True),
            _place("a", "Cầu Rồng", True)]
    result, total = search_places(rows, "CAU rong", "landmark", 2, 0)
    assert total == 3
    assert [item["poi_id"] for item in result] == ["a", "z"]
    assert normalize_text("Đà Nẵng") == "đa nang"  # Vietnamese đ is not a combining mark.


def test_snapshot_search_and_detail_include_version_and_unknown_evidence():
    snapshot = {"snapshot": "danang-test-v1", "pois": [_place("poi-1", "Biển Mỹ Khê", False)]}
    listing = search(snapshot, "bien my khe", limit=10)
    detail = get_place(snapshot, "poi-1")
    assert listing["snapshot_version"] == "danang-test-v1"
    assert listing["items"][0]["verified"] is False
    assert detail["opening_hours_state"] == detail["price_state"] == "unknown"
    assert detail["snapshot_version"] == "danang-test-v1"


def test_invalid_coordinates_and_non_boolean_verification_are_rejected():
    assert not valid_place(_place("bad", "Bad", True, lat=91))
    assert not valid_place(_place("bad", "Bad", "yes"))


def test_public_place_never_invents_missing_values():
    projection = public_place(_place("p", "A", False), "v1")
    assert projection["verified"] is False
    assert projection["source"] == "fixture"
    assert "opening_hours" not in projection


def test_default_catalog_uses_the_full_versioned_product_snapshot():
    path = _snapshot_path("data/snapshots/danang-v1")
    assert path == Path("BE/data/snapshots/danang-v1/pois.json")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot["snapshot"] == "danang-v1"
    assert len(snapshot["pois"]) == 750
    assert sum(bool(place.get("verified")) for place in snapshot["pois"]) == 549


def _load(path: Path) -> dict:
    return _load_path(str(path.resolve()), path.stat().st_mtime_ns)


def test_v1_snapshot_rows_pass_through_the_loader_unchanged():
    raw = json.loads(V1_SNAPSHOT.read_text(encoding="utf-8"))["pois"]
    assert _load(V1_SNAPSHOT)["pois"] == raw


@pytest.mark.skipif(not V2_SNAPSHOT.is_file(), reason="danang-v2 snapshot missing")
def test_v21_snapshot_serves_the_places_the_planner_plans():
    """danang-v2.1 rows keep `verified` and `cat` out of the file. The catalog derives
    them with the planner's adapter, so SNAPSHOT_DIR=danang-v2 lists every record and
    marks usable exactly the places the planner may put in a day."""
    raw = json.loads(V2_SNAPSHOT.read_text(encoding="utf-8"))["pois"]
    catalog = _load(V2_SNAPSHOT)
    rows = catalog["pois"]
    assert catalog["snapshot"] == "danang-v2"
    assert [row["poi_id"] for row in rows] == [row["poi_id"] for row in raw]
    planner = load_pois_json(str(V2_SNAPSHOT))
    assert ({row["poi_id"] for row in rows if row["verified"]}
            == {poi["poi_id"] for poi in planner if poi.get("verified")})
    assert not any(row["verified"] for row in rows
                   if row["status"] == "excluded" or row["role"] == "base")
    beaches = search(catalog, "my khe", "beach", limit=50)["items"]
    assert beaches and all(item["cat"] == "beach" for item in beaches)
    assert get_place(catalog, beaches[0]["poi_id"])["opening_hours_state"] == "known"
    excluded = next(row for row in raw if row["status"] == "excluded")
    found = search(catalog, excluded["name"], limit=50)["items"]
    assert excluded["poi_id"] not in {item["poi_id"] for item in found}
    assert get_place(catalog, excluded["poi_id"])["verified"] is False


def test_search_never_offers_an_excluded_record():
    rows = [_place("kept", "Quán A", True), _place("gone", "Quán A", False, status="excluded")]
    result, total = search_places(rows, "quan a", None, 10, 0)
    assert total == 1 and [item["poi_id"] for item in result] == ["kept"]
