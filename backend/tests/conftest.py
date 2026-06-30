from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base, create_database_engine, create_session_factory


@pytest.fixture
def sqlite_database_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def sqlite_engine(sqlite_database_url: str) -> Iterator[Engine]:
    settings = Settings(environment="test", database_url=sqlite_database_url)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(sqlite_engine: Engine) -> Iterator[Session]:
    session_factory = create_session_factory(sqlite_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
