"""SQLAlchemy models for scheduling and diagnostic workflows."""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    JSON,
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


class DiagnosticSessionStatus(StrEnum):
    ACTIVE = "active"
    READY_TO_SCHEDULE = "ready_to_schedule"
    SCHEDULED = "scheduled"
    SAFETY_ESCALATED = "safety_escalated"
    CLOSED = "closed"


class DiagnosticEventRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class CallSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


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


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_call_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    appliance_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    symptoms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DiagnosticSessionStatus.ACTIVE.value,
        index=True,
    )
    safety_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    events: Mapped[list[DiagnosticEvent]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DiagnosticEvent.id",
    )
    call_sessions: Mapped[list[CallSession]] = relationship(back_populates="diagnostic_session")


class DiagnosticEvent(Base):
    __tablename__ = "diagnostic_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    tool_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[DiagnosticSession] = relationship(back_populates="events")


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    call_sid: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CallSessionStatus.ACTIVE.value,
        index=True,
    )
    voice_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="gather")
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

    diagnostic_session: Mapped[DiagnosticSession | None] = relationship(
        back_populates="call_sessions",
        lazy="selectin",
    )
    events: Mapped[list[CallEvent]] = relationship(
        back_populates="call_session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CallEvent.id",
    )


class CallEvent(Base):
    __tablename__ = "call_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_session_id: Mapped[int] = mapped_column(
        ForeignKey("call_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    call_session: Mapped[CallSession] = relationship(back_populates="events")
