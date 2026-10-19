from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from BE.app.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_database_url: str | None = None


def _new_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def configure_database(database_url: str | None = None) -> None:
    global _engine, _session_factory, _database_url
    target_url = database_url or get_settings().database_url
    if _engine is not None:
        _engine.dispose()
    _engine = _new_engine(target_url)
    _session_factory = sessionmaker(
        bind=_engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    _database_url = target_url


def get_engine() -> Engine:
    # An explicit configure_database(url) call is authoritative until dispose.
    # Comparing it with environment settings here silently switched integration
    # tests (and any multi-database tooling) back to the default database.
    if _engine is None:
        configure_database()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def dispose_database() -> None:
    global _engine, _session_factory, _database_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _database_url = None
