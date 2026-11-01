"""Engine and transaction-scoped session factories."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    if not database_url:
        raise ValueError("DATABASE_URL is required for authoritative persistence")
    connect_args = (
        {"connect_timeout": 3}
        if database_url.startswith("postgresql+psycopg://")
        else {}
    )
    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )


@lru_cache(maxsize=4)
def get_engine(database_url: str) -> Engine:
    return create_database_engine(database_url)


@lru_cache(maxsize=4)
def get_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(database_url),
        class_=Session,
        expire_on_commit=False,
        autoflush=False,
    )


@contextmanager
def session_scope(database_url: str) -> Iterator[Session]:
    session = get_session_factory(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def clear_engine_cache() -> None:
    get_session_factory.cache_clear()
    get_engine.cache_clear()
