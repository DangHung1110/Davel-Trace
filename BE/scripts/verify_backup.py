"""Verify a PostgreSQL custom archive against its non-secret manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(archive_path: str | Path, manifest_path: str | Path) -> dict:
    archive = Path(archive_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    actual = sha256_file(archive)
    if actual != manifest.get("archive_sha256"):
        raise ValueError("backup archive checksum mismatch")
    if not manifest.get("schema_revision"):
        raise ValueError("backup manifest is missing schema revision")
    return manifest


def verify_restored_evidence(manifest: dict, actual: dict) -> None:
    for field in ("schema_revision", "counts", "representative", "relationships"):
        if actual.get(field) != manifest.get(field):
            raise ValueError(f"restored database mismatch: {field}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    result = verify_manifest(args.archive, args.manifest)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
