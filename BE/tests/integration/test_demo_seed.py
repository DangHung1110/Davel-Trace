from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from BE.app.core.config import Settings
from BE.app.db.base import Base
from BE.app.db.models import SeedRunModel
from BE.scripts.seed_demo import apply_seed, reset_seed_metadata


def test_seed_is_repeatable_and_production_is_rejected(tmp_path) -> None:
    dataset = tmp_path / "seed.json"
    dataset.write_text('{"name":"foundation-demo"}', encoding="utf-8")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    demo = Settings(app_mode="demo", _env_file=None)
    first = apply_seed(dataset, "foundation", "1", demo, factory)
    second = apply_seed(dataset, "foundation", "1", demo, factory)
    assert first["already_applied"] is False
    assert second["already_applied"] is True
    with factory() as session:
        assert session.scalar(select(func.count(SeedRunModel.seed_run_id))) == 1

    production = Settings(
        app_mode="production",
        database_url="postgresql+psycopg://davel:test@localhost/davel_trace",
        allowed_origins="https://app.example",
        _env_file=None,
    )
    with pytest.raises(RuntimeError):
        apply_seed(dataset, "foundation", "1", production, factory)


def test_demo_reset_is_scoped_to_named_seed_metadata(tmp_path) -> None:
    dataset = tmp_path / "seed.json"
    dataset.write_text('{"name":"foundation-demo"}', encoding="utf-8")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    demo = Settings(app_mode="demo", _env_file=None)
    apply_seed(dataset, "keep", "1", demo, factory)
    apply_seed(dataset, "remove", "1", demo, factory)

    result = reset_seed_metadata("remove", "1", demo, factory)

    assert result["deleted_seed_markers"] == 1
    with factory() as session:
        names = set(session.scalars(select(SeedRunModel.dataset_name)))
    assert names == {"keep"}
