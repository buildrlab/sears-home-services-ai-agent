"""SQLAlchemy models for Phase 1 scheduling reference data."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Technician(Base):
    __tablename__ = "technicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    specialties: Mapped[list[TechnicianSpecialty]] = relationship(
        back_populates="technician",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    service_areas: Mapped[list[TechnicianServiceArea]] = relationship(
        back_populates="technician",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    availability_slots: Mapped[list[AvailabilitySlot]] = relationship(
        back_populates="technician",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TechnicianSpecialty(Base):
    __tablename__ = "technician_specialties"
    __table_args__ = (
        UniqueConstraint(
            "technician_id",
            "appliance_type",
            name="uq_specialty_technician_appliance",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[int] = mapped_column(
        ForeignKey("technicians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appliance_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    technician: Mapped[Technician] = relationship(back_populates="specialties")


class TechnicianServiceArea(Base):
    __tablename__ = "technician_service_areas"
    __table_args__ = (
        UniqueConstraint("technician_id", "zip_code", name="uq_service_area_technician_zip"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[int] = mapped_column(
        ForeignKey("technicians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    technician: Mapped[Technician] = relationship(back_populates="service_areas")


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (
        UniqueConstraint(
            "technician_id",
            "day_of_week",
            "start_time",
            "end_time",
            name="uq_availability_technician_window",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    technician_id: Mapped[int] = mapped_column(
        ForeignKey("technicians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    technician: Mapped[Technician] = relationship(back_populates="availability_slots")
