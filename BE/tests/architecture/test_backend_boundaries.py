from __future__ import annotations

import ast
from pathlib import Path


MODULES = Path("BE/app/modules")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_domain_is_framework_free() -> None:
    forbidden = ("fastapi", "sqlalchemy", "BE.app.db", "BE.app.routers")
    for path in MODULES.rglob("domain.py"):
        violations = sorted(
            name for name in _imports(path) if name.startswith(forbidden)
        )
        assert not violations, f"{path} imports {violations}"


def test_application_does_not_import_transport_or_infrastructure() -> None:
    forbidden = ("fastapi", "sqlalchemy", "BE.app.db", "BE.app.routers")
    for path in MODULES.rglob("application.py"):
        violations = []
        for name in _imports(path):
            if name.startswith(forbidden) or name.endswith(".infrastructure"):
                violations.append(name)
        assert not violations, f"{path} imports {sorted(violations)}"


def test_api_and_infrastructure_do_not_cross_private_boundaries() -> None:
    for path in MODULES.rglob("api.py"):
        owner = path.parent.name
        violations = []
        for name in _imports(path):
            if name == "BE.app.db.models" or (
                ".infrastructure" in name
                and not name.startswith(f"BE.app.modules.{owner}.")
            ):
                violations.append(name)
        assert not violations, f"{path} imports {sorted(violations)}"
    for path in MODULES.rglob("infrastructure.py"):
        violations = [
            name
            for name in _imports(path)
            if name.startswith(("fastapi", "BE.app.routers"))
            or (name.endswith(".infrastructure") and name != path.as_posix())
        ]
        assert not violations, f"{path} imports {sorted(violations)}"


def test_backend_capability_graph_has_no_cycles() -> None:
    owners = {path.name for path in MODULES.iterdir() if path.is_dir()}
    graph = {owner: set() for owner in owners}
    for owner in owners:
        for path in (MODULES / owner).rglob("*.py"):
            for name in _imports(path):
                parts = name.split(".")
                if parts[:3] == ["BE", "app", "modules"] and len(parts) > 3:
                    target = parts[3]
                    if target in owners and target != owner:
                        graph[owner].add(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(owner: str) -> None:
        assert owner not in visiting, f"backend capability cycle includes {owner}"
        if owner in visited:
            return
        visiting.add(owner)
        for target in graph[owner]:
            visit(target)
        visiting.remove(owner)
        visited.add(owner)

    for owner in graph:
        visit(owner)
