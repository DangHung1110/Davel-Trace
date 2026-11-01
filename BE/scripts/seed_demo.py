"""Record deterministic demo seed application; production is fail-closed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from BE.app.core.config import AppMode, Settings, get_settings
from BE.app.db.models import SeedRunModel
from BE.app.db.session import get_session_factory


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_seed(
    dataset_path: str | Path,
    dataset_name: str,
    dataset_version: str,
    settings: Settings,
    session_factory: sessionmaker,
) -> dict:
    if settings.app_mode not in {AppMode.demo, AppMode.test}:
        raise RuntimeError("demo seed is forbidden in production mode")
    path = Path(dataset_path).resolve()
    if not path.is_file():
        raise FileNotFoundError("seed dataset does not exist")
    json.loads(path.read_text(encoding="utf-8"))
    checksum = _checksum(path)
    with session_factory() as session:
        with session.begin():
            existing = session.scalar(
                select(SeedRunModel).where(
                    SeedRunModel.dataset_name == dataset_name,
                    SeedRunModel.dataset_version == dataset_version,
                    SeedRunModel.checksum == checksum,
                    SeedRunModel.mode == settings.app_mode.value,
                )
            )
            if existing is not None:
                return {"already_applied": True, "checksum": checksum}
            session.add(
                SeedRunModel(
                    dataset_name=dataset_name,
                    dataset_version=dataset_version,
                    checksum=checksum,
                    mode=settings.app_mode.value,
                )
            )
    return {"already_applied": False, "checksum": checksum}


def reset_seed_metadata(
    dataset_name: str,
    dataset_version: str,
    settings: Settings,
    session_factory: sessionmaker,
) -> dict:
    """Remove only this named demo/test seed marker, never domain records."""
    if settings.app_mode not in {AppMode.demo, AppMode.test}:
        raise RuntimeError("demo reset is forbidden in production mode")
    with session_factory() as session:
        with session.begin():
            result = session.execute(
                delete(SeedRunModel).where(
                    SeedRunModel.dataset_name == dataset_name,
                    SeedRunModel.dataset_version == dataset_version,
                    SeedRunModel.mode == settings.app_mode.value,
                )
            )
    return {"reset": True, "deleted_seed_markers": int(result.rowcount or 0)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--name", default="foundation-demo")
    parser.add_argument("--version", default="1")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required for seed")
    factory = get_session_factory(settings.database_url)
    if args.reset:
        result = reset_seed_metadata(args.name, args.version, settings, factory)
    else:
        result = apply_seed(
            args.dataset,
            args.name,
            args.version,
            settings,
            factory,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
