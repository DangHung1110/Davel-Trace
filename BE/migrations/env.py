from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from BE.app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if os.getenv("DAVEL_DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.environ["DAVEL_DATABASE_URL"])

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            # SQLAlchemy 2 starts an implicit transaction for PRAGMA. Close it
            # before Alembic opens its own migration transaction, otherwise the
            # version-row writes and later SQLite DDL are rolled back on close.
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
