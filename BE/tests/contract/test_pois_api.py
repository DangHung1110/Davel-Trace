def test_poi_catalog_searches_shared_snapshot_records(client):
    response = client.get("/v1/pois?q=rong&limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"] == "danang-v1"
    assert any("Rồng" in item["name"] for item in payload["items"])


def test_verified_filter_does_not_promote_unreviewed_records(client):
    response = client.get("/v1/pois?q=rong&verified_only=true")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_poi_limit_is_bounded(client):
    assert client.get("/v1/pois?limit=0").status_code == 422
    assert client.get("/v1/pois?limit=51").status_code == 422
