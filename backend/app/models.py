"""SQLAlchemy models for scheduling and diagnostic workflows."""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppointmentStatus(StrEnum):
    HELD = "held"
    BOOKED = "booked"
    CANCELLED = "cancelled"


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
    appointments: Mapped[list[Appointment]] = relationship(back_populates="technician")


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


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    technician_id: Mapped[int] = mapped_column(
        ForeignKey("technicians.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    appliance_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    issue_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=AppointmentStatus.HELD.value,
        index=True,
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    active_slot_key: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        unique=True,
    )
    confirmation_code: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer: Mapped[Customer] = relationship(back_populates="appointments", lazy="selectin")
    technician: Mapped[Technician] = relationship(back_populates="appointments", lazy="selectin")
