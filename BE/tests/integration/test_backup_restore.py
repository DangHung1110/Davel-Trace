from __future__ import annotations

import json

import pytest

from BE.scripts.verify_backup import (
    sha256_file,
    verify_manifest,
    verify_restored_evidence,
)


def test_backup_manifest_detects_archive_changes(tmp_path) -> None:
    archive = tmp_path / "database.dump"
    archive.write_bytes(b"davel-backup")
    manifest = tmp_path / "database.dump.json"
    manifest.write_text(
        json.dumps({"archive_sha256": sha256_file(archive), "schema_revision": "005_001"}),
        encoding="utf-8",
    )
    assert verify_manifest(archive, manifest)["schema_revision"] == "005_001"
    archive.write_bytes(b"changed")
    with pytest.raises(ValueError):
        verify_manifest(archive, manifest)


def test_restored_evidence_requires_revision_counts_and_representative_ids() -> None:
    expected = {
        "schema_revision": "005_001",
        "counts": {"acceptance_records": 2},
        "representative": {"acceptance_id": "0001"},
        "relationships": {
            "acceptance_id": "0001",
            "parent_acceptance_id": None,
            "shadow_observation_id": "shadow-1",
            "trip_id": "trip-1",
            "itinerary_id": "it-1",
        },
    }
    verify_restored_evidence(expected, dict(expected))
    changed = {**expected, "counts": {"acceptance_records": 1}}
    with pytest.raises(ValueError, match="counts"):
        verify_restored_evidence(expected, changed)
