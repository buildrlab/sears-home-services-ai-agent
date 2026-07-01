from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_from_empty_database(sqlite_database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url)

    command.upgrade(config, "head")

    engine = create_engine(sqlite_database_url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= {
            "alembic_version",
            "technicians",
            "technician_specialties",
            "technician_service_areas",
            "availability_slots",
            "customers",
            "appointments",
            "diagnostic_sessions",
            "diagnostic_events",
            "call_sessions",
            "call_events",
            "image_uploads",
        }
    finally:
        engine.dispose()


def test_initial_migration_is_present() -> None:
    migration_path = Path("alembic/versions/0001_create_technician_reference_schema.py")

    assert migration_path.is_file()


def test_appointment_migration_is_present() -> None:
    migration_path = Path("alembic/versions/0002_create_customer_appointment_schema.py")

    assert migration_path.is_file()


def test_diagnostic_migration_is_present() -> None:
    migration_path = Path("alembic/versions/0003_create_diagnostic_session_schema.py")

    assert migration_path.is_file()


def test_call_session_migration_is_present() -> None:
    migration_path = Path("alembic/versions/0004_create_call_session_schema.py")

    assert migration_path.is_file()


def test_image_upload_migration_is_present() -> None:
    migration_path = Path("alembic/versions/0005_create_image_upload_schema.py")

    assert migration_path.is_file()
