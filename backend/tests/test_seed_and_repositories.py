from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AvailabilitySlot, TechnicianServiceArea, TechnicianSpecialty
from app.repositories import TechnicianRepository
from app.seed import SEED_TECHNICIANS, seed_reference_data


def test_seed_reference_data_is_idempotent(db_session: Session) -> None:
    first_count = seed_reference_data(db_session)
    db_session.commit()
    second_count = seed_reference_data(db_session)
    db_session.commit()

    specialty_count = db_session.execute(
        select(func.count()).select_from(TechnicianSpecialty)
    ).scalar_one()
    service_area_count = db_session.execute(
        select(func.count()).select_from(TechnicianServiceArea)
    ).scalar_one()
    availability_count = db_session.execute(
        select(func.count()).select_from(AvailabilitySlot)
    ).scalar_one()

    assert first_count == len(SEED_TECHNICIANS)
    assert second_count == len(SEED_TECHNICIANS)
    assert specialty_count == sum(len(technician.specialties) for technician in SEED_TECHNICIANS)
    assert service_area_count == sum(
        len(technician.service_areas) for technician in SEED_TECHNICIANS
    )
    assert availability_count == sum(
        len(technician.availability) for technician in SEED_TECHNICIANS
    )


def test_repository_lists_seeded_active_technicians(db_session: Session) -> None:
    seed_reference_data(db_session)
    db_session.commit()
    repository = TechnicianRepository(db_session)

    technicians = repository.list_active()

    assert repository.count_active() == len(SEED_TECHNICIANS)
    assert [technician.name for technician in technicians] == sorted(
        technician.name for technician in SEED_TECHNICIANS
    )


def test_repository_matches_technicians_by_zip_and_appliance(db_session: Session) -> None:
    seed_reference_data(db_session)
    db_session.commit()
    repository = TechnicianRepository(db_session)

    matches = repository.find_by_zip_and_appliance(
        zip_code="75201",
        appliance_type="REFRIGERATOR",
    )

    assert len(matches) == 1
    assert matches[0].name == "Avery Johnson"
    assert "refrigerator" in matches[0].specialties
    assert "75201" in matches[0].service_areas
    assert len(matches[0].availability) == 2


def test_repository_returns_empty_list_when_no_technician_matches(db_session: Session) -> None:
    seed_reference_data(db_session)
    db_session.commit()
    repository = TechnicianRepository(db_session)

    matches = repository.find_by_zip_and_appliance(zip_code="99999", appliance_type="washer")

    assert matches == []
