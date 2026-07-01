"""Database engine, session, and declarative base helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


def create_database_engine(settings: Settings | None = None) -> Engine:
    runtime_settings = settings or get_settings()
    kwargs: dict[str, object] = {
        "echo": runtime_settings.database_echo,
        "pool_pre_ping": True,
    }
    database_url = runtime_settings.sqlalchemy_database_url
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


engine = create_database_engine()
SessionLocal = create_session_factory(engine)


@contextmanager
def session_scope(session_factory: sessionmaker[Session] = SessionLocal) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
