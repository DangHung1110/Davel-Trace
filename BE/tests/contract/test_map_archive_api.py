from fastapi.testclient import TestClient

from BE.app.main import app
from BE.app.modules.routing import api


def test_map_archive_supports_real_byte_ranges_and_browser_headers():
    response = TestClient(app).get('/v1/maps/danang.pmtiles', headers={
        'Range': 'bytes=0-15', 'Origin': 'http://127.0.0.1:5501',
    })
    assert response.status_code == 206
    assert len(response.content) == 16
    assert response.content.startswith(b'PMTiles')
    assert response.headers['content-range'] == f'bytes 0-15/{api.MAP_ARCHIVE_PATH.stat().st_size}'
    assert response.headers['accept-ranges'] == 'bytes'
    assert response.headers['content-length'] == '16'
    assert response.headers['access-control-allow-origin'] == 'http://127.0.0.1:5501'
    assert 'ETag' in response.headers['access-control-expose-headers']


def test_map_archive_rejects_unsatisfiable_range_and_allows_cors_preflight():
    client = TestClient(app)
    assert client.get('/v1/maps/danang.pmtiles', headers={'Range': 'bytes=999999999-'}).status_code == 416
    response = client.options('/v1/maps/danang.pmtiles', headers={
        'Origin': 'http://127.0.0.1:5501', 'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'Range,If-Match,If-Range',
    })
    assert response.status_code == 200


def test_missing_archive_reports_unavailable_without_exposing_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'MAP_ARCHIVE_PATH', tmp_path / 'missing.pmtiles')
    response = TestClient(app).get('/v1/maps/danang.pmtiles')
    assert response.status_code == 503
    assert str(tmp_path) not in response.text
