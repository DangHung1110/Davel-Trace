import json
from pathlib import Path

from BE.app.modules.catalog.application import get_place, search
from BE.app.modules.catalog.domain import normalize_text, public_place, search_places, valid_place
from BE.app.modules.catalog.infrastructure import _snapshot_path


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
    assert len(snapshot["pois"]) == 742
    assert sum(bool(place.get("verified")) for place in snapshot["pois"]) == 48
