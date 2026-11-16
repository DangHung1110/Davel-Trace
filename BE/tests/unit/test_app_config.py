"""CORS and router exposure per environment (audit N6).

Run from repo root: python -m pytest BE/tests/unit/test_app_config.py -q
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from BE.app.config import Settings  # noqa: E402
from BE.app.main import configure  # noqa: E402

APP_ORIGIN = "https://davel-trace.example"
# Production settings refuse to load without an authoritative database URL.
PROD_DB = "postgresql+psycopg://davel:test@127.0.0.1:5432/davel_trace"
PRODUCTION = {"app_mode": "production", "allowed_origins": APP_ORIGIN,
              "database_url": PROD_DB}


def client(**settings) -> TestClient:
    app = FastAPI()
    configure(app, Settings(_env_file=None, **settings))
    return TestClient(app)


def preflight(test_client: TestClient, origin: str, method: str = "POST"):
    return test_client.options("/v1/parse", headers={
        "Origin": origin, "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "content-type"})


def allowed(test_client: TestClient, origin: str) -> bool:
    return preflight(test_client, origin).headers.get("access-control-allow-origin") == origin


class TestCors(unittest.TestCase):
    def test_no_wildcard_in_local_mode(self):
        local = client()
        self.assertTrue(allowed(local, "http://localhost:5500"))
        self.assertTrue(allowed(local, "http://127.0.0.1:8080"))
        self.assertFalse(allowed(local, "https://evil.example"))
        self.assertFalse(allowed(local, "http://localhost.evil.example"))

    def test_production_only_answers_its_own_origin(self):
        prod = client(**PRODUCTION)
        self.assertTrue(allowed(prod, APP_ORIGIN))
        self.assertFalse(allowed(prod, "http://localhost:5500"))

    def test_only_the_methods_the_api_has(self):
        # The product platform's trips/expenses/identity routes use PUT, PATCH
        # and DELETE; nothing answers TRACE.
        self.assertEqual(preflight(client(), "http://localhost:5500", "DELETE").status_code, 200)
        self.assertEqual(preflight(client(), "http://localhost:5500", "TRACE").status_code, 400)


class TestRouters(unittest.TestCase):
    def paths(self, **settings) -> set[str]:
        return set(client(**settings).app.openapi()["paths"])

    def test_local_routers_stay_out_of_production(self):
        for path in ("/v1/repair", "/v1/review", "/v1/accept"):
            self.assertIn(path, self.paths())
            self.assertNotIn(path, self.paths(**PRODUCTION))

    def test_public_routers_are_always_on(self):
        self.assertIn("/v1/itinerary", self.paths(**PRODUCTION))


class TestEnv(unittest.TestCase):
    def test_settings_read_the_environment(self):
        with mock.patch.dict(os.environ, {"APP_MODE": "production",
                                          "DATABASE_URL": PROD_DB,
                                          "ALLOWED_ORIGINS": f" {APP_ORIGIN}, https://b.example ,"}):
            settings = Settings(_env_file=None)
        self.assertTrue(settings.is_production)
        self.assertEqual(settings.cors_origins, [APP_ORIGIN, "https://b.example"])


if __name__ == "__main__":
    unittest.main()
