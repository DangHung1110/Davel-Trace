from BE.app.modules.catalog.application import resolve_name_candidates


def test_resolves_abbreviated_names_without_treating_all_museums_as_candidates():
    places = [
        {"poi_id": "cham", "name": "Bảo tàng Điêu khắc Chăm Đà Nẵng", "verified": True},
        {"poi_id": "museum", "name": "Bảo tàng Đà Nẵng", "verified": True},
    ]
    assert [row["poi_id"] for row in resolve_name_candidates(places, "Bảo tàng Chăm")] == ["cham"]


def test_exact_name_beats_partial_names_with_case_accents_and_punctuation():
    places = [
        {"poi_id": "museum", "name": "Bảo tàng Đà Nẵng", "verified": True},
        {"poi_id": "shop", "name": "Quán cạnh Bảo tàng Đà Nẵng", "verified": True},
    ]
    assert [row["poi_id"] for row in resolve_name_candidates(places, "  BAO TANG, DA NANG! ")] == ["museum"]


def test_duplicate_exact_names_remain_ambiguous_and_ids_are_deduplicated():
    places = [
        {"poi_id": "a", "name": "An", "verified": True},
        {"poi_id": "b", "name": "An", "verified": True},
        {"poi_id": "a", "name": "An", "verified": True},
        {"poi_id": "c", "name": "An Coffee", "verified": True},
    ]
    assert [row["poi_id"] for row in resolve_name_candidates(places, "an")] == ["a", "b"]


def test_partial_name_matching_uses_word_boundaries_and_only_verified_records():
    places = [
        {"poi_id": "a", "name": "Biển Mỹ Khê", "verified": True},
        {"poi_id": "b", "name": "Biển Mỹ Khê phía Nam", "verified": True},
        {"poi_id": "c", "name": "Mỹ Khê chưa xác minh", "verified": False},
        {"poi_id": "d", "name": "Mỹ Khê thiếu xác minh"},
        {"poi_id": "e", "name": "Tamỹ Khê", "verified": True},
    ]
    assert [row["poi_id"] for row in resolve_name_candidates(places, "my khe")] == ["a", "b"]
    assert resolve_name_candidates(places, "không có") == []
    assert resolve_name_candidates(places, "!!!") == []


def test_catalog_aliases_can_resolve_a_name_without_ever_exposing_them_to_ai():
    places = [{"poi_id": "bridge", "name": "Cầu Rồng", "aliases": ["Dragon Bridge"], "verified": True}]
    assert resolve_name_candidates(places, "dragon bridge") == places
