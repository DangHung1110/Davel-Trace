"""Security sweep (T059, lane C). No secrets/API keys in tracked files.

Scans `git ls-files` content for secret patterns (allowlisting obvious
fakes: test/fake/example/placeholder), asserts BE/.env is untracked +
gitignored, and no key/token is printed or embedded in credential URLs.

Run from repo root: python BE/tests/unit/test_no_secrets.py -v
"""

import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

REPO = os.path.join(os.path.dirname(__file__), "..", "..", "..")

PATTERNS = [
    r"sk-[A-Za-z0-9]{8,}",
    r"AIza[A-Za-z0-9_-]{10,}",
    r"xox[bap]-[A-Za-z0-9-]{8,}",
    r"ghp_[A-Za-z0-9]{8,}",
    r"password\s*=\s*['\"][^'\"]{3,}",
    r"Bearer [A-Za-z0-9._-]{12,}",
    r"https?://[^/\s]*:[^/\s]*@[A-Za-z]",
]
ALLOW = re.compile(r"test|fake|example|placeholder|xxx|sk-test", re.IGNORECASE)
SKIP_EXT = (".png", ".jpg", ".pyc", ".pmtiles", ".exe", ".lock")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    return [f for f in out if not f.endswith(SKIP_EXT)]


class TestNoSecrets(unittest.TestCase):
    def test_no_secret_patterns(self):
        hits = []
        for f in tracked_files():
            p = os.path.join(REPO, f)
            if not os.path.isfile(p):
                continue
            try:
                with open(p, encoding="utf-8", errors="strict") as fh:
                    text = fh.read()
            except (UnicodeDecodeError, ValueError):
                continue
            for pat in PATTERNS:
                for m in re.finditer(pat, text):
                    line = text[max(0, m.start() - 60):m.end() + 20]
                    if not ALLOW.search(line):
                        hits.append(f"{f}: {pat} :: {line.strip()[:100]}")
        self.assertEqual(hits, [], f"possible secrets:\n" + "\n".join(hits[:10]))

    def test_env_excluded(self):
        out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                             text=True, check=True).stdout.splitlines()
        envs = [f for f in out if os.path.basename(f) == ".env"]
        self.assertEqual(envs, [], "BE/.env must never be tracked")
        chk = subprocess.run(["git", "check-ignore", "BE/.env"], cwd=REPO,
                             capture_output=True, text=True)
        self.assertEqual(chk.returncode, 0, "BE/.env must be gitignored")


if __name__ == "__main__":
    unittest.main()
