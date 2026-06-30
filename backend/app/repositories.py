"""Repository helpers for technician reference data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Technician, TechnicianServiceArea, TechnicianSpecialty


@dataclass(frozen=True)
class TechnicianMatch:
    id: int
    name: str
    email: str
    specialties: tuple[str, ...]
    service_areas: tuple[str, ...]


class TechnicianRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_active(self) -> int:
        statement = select(func.count()).select_from(Technician).where(Technician.active.is_(True))
        return int(self._session.execute(statement).scalar_one())

    def list_active(self) -> list[Technician]:
        statement = (
            select(Technician)
            .where(Technician.active.is_(True))
            .options(
                selectinload(Technician.specialties),
                selectinload(Technician.service_areas),
                selectinload(Technician.availability_slots),
            )
            .order_by(Technician.name)
        )
        return list(self._session.scalars(statement).unique())

    def find_by_zip_and_appliance(
        self,
        *,
        zip_code: str,
        appliance_type: str,
    ) -> list[TechnicianMatch]:
        normalized_appliance = appliance_type.strip().lower()
        normalized_zip = zip_code.strip()
        statement = (
            select(Technician)
            .join(Technician.service_areas)
            .join(Technician.specialties)
            .where(
                Technician.active.is_(True),
                TechnicianServiceArea.zip_code == normalized_zip,
                func.lower(TechnicianSpecialty.appliance_type) == normalized_appliance,
            )
            .options(
                selectinload(Technician.specialties),
                selectinload(Technician.service_areas),
            )
            .order_by(Technician.name)
        )
        technicians = self._session.scalars(statement).unique().all()
        return [
            TechnicianMatch(
                id=technician.id,
                name=technician.name,
                email=technician.email,
                specialties=tuple(
                    sorted(specialty.appliance_type for specialty in technician.specialties)
                ),
                service_areas=tuple(sorted(area.zip_code for area in technician.service_areas)),
            )
            for technician in technicians
        ]
