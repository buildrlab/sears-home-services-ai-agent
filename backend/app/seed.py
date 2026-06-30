"""Reference seed data for local scheduling development."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import session_scope
from app.models import AvailabilitySlot, Technician, TechnicianServiceArea, TechnicianSpecialty


@dataclass(frozen=True)
class SeedTechnician:
    name: str
    email: str
    specialties: tuple[str, ...]
    service_areas: tuple[str, ...]
    availability: tuple[tuple[int, time, time], ...]


SEED_TECHNICIANS: tuple[SeedTechnician, ...] = (
    SeedTechnician(
        name="Avery Johnson",
        email="avery.johnson@example.test",
        specialties=("refrigerator", "washer"),
        service_areas=("75201", "75204"),
        availability=((0, time(8), time(12)), (2, time(13), time(17))),
    ),
    SeedTechnician(
        name="Blake Martinez",
        email="blake.martinez@example.test",
        specialties=("dryer", "dishwasher"),
        service_areas=("76102", "76107"),
        availability=((1, time(8), time(12)), (3, time(12), time(16))),
    ),
    SeedTechnician(
        name="Casey Nguyen",
        email="casey.nguyen@example.test",
        specialties=("oven", "range"),
        service_areas=("78701", "78704"),
        availability=((0, time(12), time(16)), (4, time(8), time(12))),
    ),
    SeedTechnician(
        name="Drew Patel",
        email="drew.patel@example.test",
        specialties=("freezer", "refrigerator"),
        service_areas=("77002", "77008"),
        availability=((2, time(8), time(12)), (4, time(13), time(17))),
    ),
    SeedTechnician(
        name="Emerson Garcia",
        email="emerson.garcia@example.test",
        specialties=("washer", "dryer"),
        service_areas=("78205", "78212"),
        availability=((1, time(13), time(17)), (3, time(8), time(12))),
    ),
    SeedTechnician(
        name="Finley Brooks",
        email="finley.brooks@example.test",
        specialties=("dishwasher", "oven"),
        service_areas=("75024", "75093"),
        availability=((0, time(9), time(13)), (2, time(12), time(16))),
    ),
)


def seed_reference_data(session: Session) -> int:
    """Insert deterministic technician reference data if it is missing."""

    inserted_or_seen = 0
    for seed_technician in SEED_TECHNICIANS:
        technician = _get_or_create_technician(session, seed_technician)
        _ensure_specialties(session, technician, seed_technician.specialties)
        _ensure_service_areas(session, technician, seed_technician.service_areas)
        _ensure_availability(session, technician, seed_technician.availability)
        inserted_or_seen += 1
    session.flush()
    return inserted_or_seen


def _get_or_create_technician(session: Session, seed_technician: SeedTechnician) -> Technician:
    statement = select(Technician).where(Technician.email == seed_technician.email)
    technician = session.scalars(statement).one_or_none()
    if technician is not None:
        technician.name = seed_technician.name
        technician.active = True
        return technician

    technician = Technician(
        name=seed_technician.name,
        email=seed_technician.email,
        active=True,
    )
    session.add(technician)
    session.flush()
    return technician


def _ensure_specialties(
    session: Session, technician: Technician, appliance_types: tuple[str, ...]
) -> None:
    existing = {specialty.appliance_type for specialty in technician.specialties}
    for appliance_type in appliance_types:
        if appliance_type in existing:
            continue
        session.add(
            TechnicianSpecialty(
                technician_id=technician.id,
                appliance_type=appliance_type,
            )
        )


def _ensure_service_areas(
    session: Session,
    technician: Technician,
    zip_codes: tuple[str, ...],
) -> None:
    existing = {area.zip_code for area in technician.service_areas}
    for zip_code in zip_codes:
        if zip_code in existing:
            continue
        session.add(TechnicianServiceArea(technician_id=technician.id, zip_code=zip_code))


def _ensure_availability(
    session: Session,
    technician: Technician,
    availability: tuple[tuple[int, time, time], ...],
) -> None:
    existing = {
        (slot.day_of_week, slot.start_time, slot.end_time)
        for slot in technician.availability_slots
    }
    for day_of_week, start_time, end_time in availability:
        if (day_of_week, start_time, end_time) in existing:
            continue
        session.add(
            AvailabilitySlot(
                technician_id=technician.id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                capacity=1,
            )
        )


def main() -> int:
    with session_scope() as session:
        count = seed_reference_data(session)
    print(f"Seeded or verified {count} technicians.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
