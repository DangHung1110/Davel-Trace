from __future__ import annotations

import threading
import urllib.request
from http.server import ThreadingHTTPServer

from server import RangeRequestHandler


def test_pmtiles_byte_range_stays_available() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/data/danang.pmtiles",
            headers={"Range": "bytes=0-99"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 206
            assert response.headers["Content-Range"].startswith("bytes 0-99/")
            assert len(response.read()) == 100
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_root_map_keeps_search_route_fallback_and_playback_assets() -> None:
    source = open("index.html", encoding="utf-8").read()
    for marker in (
        "data/danang.pmtiles",
        "requestPhotonSearch",
        "router.project-osrm.org/route/v1/driving",
        "VietMap Routing",
        "playRoute",
        "pausedProgress",
        "Đường cam chỉ là nội suy",
    ):
        assert marker in source
