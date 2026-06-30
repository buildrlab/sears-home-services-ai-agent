"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.database import session_scope


def get_db_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session
