"""Unit test for LLM gateway (T005). Mock transports only.

Covers: valid JSON first-try, garbage-then-valid (retry heals),
always-garbage (clear bad_json error), transport-error-then-success,
schema validation + retry, api-provider auth header from env (no
hardcoded key). Live Ollama smoke is manual/optional, not asserted.

Run from repo root: python BE/tests/unit/test_llm.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import BaseModel  # noqa: E402

from BE.app.config import Settings  # noqa: E402
from BE.app.services.llm import LLMError, complete_json  # noqa: E402


class TripSlots(BaseModel):
    city: str
    days: int


def ok_transport(url, headers, body):
    assert body["options"]["temperature"] == 0.1
    return {"text": '{"city": "da-nang", "days": 2}'}


def flaky_then_ok():
    calls = {"n": 0}

    def run(url, headers, body):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"text": "chac la Da Nang 2 ngay!!!"}
        return {"text": '{"city": "da-nang", "days": 2}'}
    run.calls = calls
    return run


def always_garbage(url, headers, body):
    return {"text": "no json here"}


def down_then_up(url, headers, body):
    down_then_up.n = getattr(down_then_up, "n", 0) + 1
    if down_then_up.n == 1:
        raise ConnectionError("ollama not running")
    return {"text": '{"city": "da-nang", "days": 2}'}


def bad_schema(url, headers, body):
    return {"text": '{"city": "da-nang"}'}  # missing days


def blank_ints_transport(url, headers, body):
    """qwen3 quirk: empty strings where the schema wants numbers."""
    return {"text": '{"city": "da-nang", "days": "", "travelers": "", '
                    '"budget": "3000000"}'}


LOCAL = Settings(llm_provider="local", ollama_url="http://x:11434")


class TestLLM(unittest.TestCase):
    def test_valid_first_try(self):
        out = complete_json("p", TripSlots, ok_transport, LOCAL)
        self.assertEqual(out, {"city": "da-nang", "days": 2})

    def test_ollama_request_body_has_stream_false_and_json_format(self):
        seen = {}

        def run(url, headers, body):
            seen.update(body)
            return {"text": '{"city": "da-nang", "days": 2}'}

        complete_json("p", TripSlots, run, LOCAL)

        self.assertEqual(seen["stream"], False)
        self.assertEqual(seen["format"], "json")
        self.assertEqual(seen["options"], {"temperature": 0.1})
        self.assertNotIn("temperature", seen)

    def test_retry_heals_garbage(self):
        t = flaky_then_ok()
        out = complete_json("p", TripSlots, t, LOCAL)
        self.assertEqual(out["days"], 2)
        self.assertEqual(t.calls["n"], 2)

    def test_exhausted_retries_clear_error(self):
        with self.assertRaises(LLMError) as cm:
            complete_json("p", TripSlots, always_garbage, LOCAL)
        self.assertEqual(cm.exception.reason, "bad_json")

    def test_transport_retry(self):
        down_then_up.n = 0
        out = complete_json("p", TripSlots, down_then_up, LOCAL)
        self.assertEqual(out["city"], "da-nang")

    def test_schema_mismatch_retries_then_fails(self):
        with self.assertRaises(LLMError) as cm:
            complete_json("p", TripSlots, bad_schema, LOCAL)
        self.assertEqual(cm.exception.reason, "schema")

    def test_parser_schema_normalises_blank_ints_before_validation(self):
        """Live regression: travelers "" must not retry 3x -> 503.

        `complete_json` validates against the Pydantic schema BEFORE `parse`
        can normalise the dict, so the schema itself must accept blanks.
        """
        from BE.app.services.parser import TripSlots as ParserSlots

        out = complete_json("p", ParserSlots, blank_ints_transport, LOCAL)
        self.assertIsNone(out["travelers"])
        self.assertIsNone(out["days"])
        self.assertEqual(out["budget"], 3000000)

    def test_api_provider_uses_env_key(self):
        seen = {}

        def run(url, headers, body):
            seen.update(url=url, headers=headers, body=body)
            return {"text": '{"city": "da-nang", "days": 1}'}
        os.environ["LLM_API_KEY"] = "sk-test-fake"
        try:
            out = complete_json("p", TripSlots, run,
                                Settings(llm_provider="api"))
        finally:
            del os.environ["LLM_API_KEY"]
        self.assertEqual(out["days"], 1)
        self.assertIn("/chat/completions", seen["url"])
        self.assertEqual(seen["headers"]["Authorization"], "Bearer sk-test-fake")
        self.assertEqual(seen["body"]["temperature"], 0.1)


if __name__ == "__main__":
    unittest.main()
