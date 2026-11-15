from __future__ import annotations

import re
from pathlib import Path


FEATURES = Path("FE/lib/features")
IMPORT = re.compile(r"(?:import|export)\s+['\"]([^'\"]+)['\"]")


def test_flutter_domain_is_widget_and_http_free() -> None:
    forbidden = ("package:flutter/", "package:http/", "/presentation/", "/data/")
    for path in FEATURES.rglob("domain/*.dart"):
        source = path.read_text(encoding="utf-8")
        violations = [token for token in forbidden if token in source]
        assert not violations, f"{path} contains {violations}"


def test_features_do_not_import_other_private_layers() -> None:
    for path in FEATURES.rglob("*.dart"):
        owner = path.relative_to(FEATURES).parts[0]
        for target in IMPORT.findall(path.read_text(encoding="utf-8")):
            if not target.startswith("."):
                continue
            resolved = (path.parent / target).resolve()
            try:
                relative = resolved.relative_to(FEATURES.resolve())
            except ValueError:
                continue
            target_owner = relative.parts[0]
            if target_owner != owner:
                private = set(relative.parts[1:]) & {"data", "presentation"}
                assert not private, f"{path} imports private feature path {target}"


def test_flutter_data_and_core_dependencies_point_inward() -> None:
    for path in FEATURES.rglob("data/*.dart"):
        source = path.read_text(encoding="utf-8")
        assert "/presentation/" not in source
        assert "package:flutter/material.dart" not in source
    core = Path("FE/lib/core")
    for path in core.rglob("*.dart"):
        assert "features/" not in path.read_text(encoding="utf-8")


def test_flutter_feature_graph_has_no_cycles() -> None:
    owners = {path.name for path in FEATURES.iterdir() if path.is_dir()}
    graph = {owner: set() for owner in owners}
    for path in FEATURES.rglob("*.dart"):
        owner = path.relative_to(FEATURES).parts[0]
        for target in IMPORT.findall(path.read_text(encoding="utf-8")):
            if not target.startswith("."):
                continue
            resolved = (path.parent / target).resolve()
            try:
                target_owner = resolved.relative_to(FEATURES.resolve()).parts[0]
            except ValueError:
                continue
            if target_owner in owners and target_owner != owner:
                graph[owner].add(target_owner)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(owner: str) -> None:
        assert owner not in visiting, f"Flutter feature cycle includes {owner}"
        if owner in visited:
            return
        visiting.add(owner)
        for target in graph[owner]:
            visit(target)
        visiting.remove(owner)
        visited.add(owner)

    for owner in graph:
        visit(owner)
