"""Transactional scheduling service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import token_hex

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.exceptions import (
    AppointmentNotFoundError,
    InvalidSchedulingRequestError,
    SlotUnavailableError,
)
from app.models import Appointment, AppointmentStatus, Customer, Technician
from app.repositories import TechnicianMatch, TechnicianRepository
from app.schemas import AppointmentHoldRequest, CustomerCreate


class SchedulingService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_matches(self, *, zip_code: str, appliance_type: str) -> list[TechnicianMatch]:
        return TechnicianRepository(self._session).find_by_zip_and_appliance(
            zip_code=zip_code,
            appliance_type=appliance_type,
        )

    def create_hold(self, request: AppointmentHoldRequest) -> Appointment:
        now = _utc_now()
        self._release_expired_holds(now)

        technician = self._get_active_technician(request.technician_id)
        normalized_appliance = request.appliance_type.strip().lower()
        normalized_zip = request.zip_code.strip()
        scheduled_start = _to_utc_minute(request.scheduled_start)
        scheduled_end = scheduled_start + timedelta(minutes=request.duration_minutes)

        self._validate_technician_match(
            technician=technician,
            zip_code=normalized_zip,
            appliance_type=normalized_appliance,
        )
        self._validate_availability_window(
            technician=technician,
            scheduled_start=request.scheduled_start,
            duration_minutes=request.duration_minutes,
        )

        customer = self._get_or_create_customer(request.customer)
        appointment = Appointment(
            customer_id=customer.id,
            technician_id=technician.id,
            appliance_type=normalized_appliance,
            zip_code=normalized_zip,
            issue_summary=request.issue_summary,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status=AppointmentStatus.HELD.value,
            hold_expires_at=now + timedelta(minutes=request.hold_minutes),
            active_slot_key=_active_slot_key(technician.id, scheduled_start),
        )
        self._session.add(appointment)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise SlotUnavailableError(
                "The requested appointment slot is no longer available."
            ) from exc
        return self.get_appointment(appointment.id)

    def book_appointment(self, appointment_id: int) -> Appointment:
        now = _utc_now()
        self._release_expired_holds(now)
        appointment = self.get_appointment(appointment_id)

        if appointment.status == AppointmentStatus.BOOKED.value:
            return appointment
        if appointment.status != AppointmentStatus.HELD.value:
            raise InvalidSchedulingRequestError("Only held appointments can be booked.")
        if appointment.hold_expires_at and _to_utc(appointment.hold_expires_at) <= now:
            appointment.status = AppointmentStatus.CANCELLED.value
            appointment.active_slot_key = None
            self._session.flush()
            raise SlotUnavailableError("The appointment hold has expired.")

        appointment.status = AppointmentStatus.BOOKED.value
        appointment.hold_expires_at = None
        appointment.confirmation_code = appointment.confirmation_code or _confirmation_code()
        self._session.flush()
        return self.get_appointment(appointment.id)

    def cancel_appointment(self, appointment_id: int) -> Appointment:
        appointment = self.get_appointment(appointment_id)
        if appointment.status != AppointmentStatus.CANCELLED.value:
            appointment.status = AppointmentStatus.CANCELLED.value
            appointment.hold_expires_at = None
            appointment.active_slot_key = None
            self._session.flush()
        return self.get_appointment(appointment.id)

    def get_appointment(self, appointment_id: int) -> Appointment:
        statement = (
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .options(selectinload(Appointment.customer), selectinload(Appointment.technician))
        )
        appointment = self._session.scalars(statement).one_or_none()
        if appointment is None:
            raise AppointmentNotFoundError("Appointment not found.")
        return appointment

    def list_appointments(self, *, status: AppointmentStatus | None = None) -> list[Appointment]:
        statement = select(Appointment).options(
            selectinload(Appointment.customer),
            selectinload(Appointment.technician),
        )
        if status is not None:
            statement = statement.where(Appointment.status == status.value)
        statement = statement.order_by(Appointment.scheduled_start, Appointment.id)
        return list(self._session.scalars(statement).all())

    def _get_active_technician(self, technician_id: int) -> Technician:
        statement = (
            select(Technician)
            .where(Technician.id == technician_id, Technician.active.is_(True))
            .options(
                selectinload(Technician.specialties),
                selectinload(Technician.service_areas),
                selectinload(Technician.availability_slots),
            )
        )
        technician = self._session.scalars(statement).one_or_none()
        if technician is None:
            raise InvalidSchedulingRequestError("Technician is unavailable.")
        return technician

    def _validate_technician_match(
        self,
        *,
        technician: Technician,
        zip_code: str,
        appliance_type: str,
    ) -> None:
        if zip_code not in {area.zip_code for area in technician.service_areas}:
            raise InvalidSchedulingRequestError(
                "Technician does not service the requested ZIP code."
            )
        if appliance_type not in {
            specialty.appliance_type.lower() for specialty in technician.specialties
        }:
            raise InvalidSchedulingRequestError(
                "Technician does not support the requested appliance type."
            )

    def _validate_availability_window(
        self,
        *,
        technician: Technician,
        scheduled_start: datetime,
        duration_minutes: int,
    ) -> None:
        local_end = scheduled_start + timedelta(minutes=duration_minutes)
        if local_end.date() != scheduled_start.date():
            raise InvalidSchedulingRequestError("Appointment must fit within one availability day.")

        start_time = scheduled_start.timetz().replace(tzinfo=None)
        end_time = local_end.timetz().replace(tzinfo=None)
        for slot in technician.availability_slots:
            if (
                slot.day_of_week == scheduled_start.weekday()
                and slot.start_time <= start_time
                and slot.end_time >= end_time
            ):
                return
        raise InvalidSchedulingRequestError("Technician is not available for the requested time.")

    def _get_or_create_customer(self, request: CustomerCreate) -> Customer:
        normalized_email = request.email.strip().lower() if request.email else None
        normalized_phone = request.phone.strip() if request.phone else None

        customer = self._find_existing_customer(email=normalized_email, phone=normalized_phone)
        if customer is not None:
            customer.full_name = request.full_name.strip()
            customer.email = normalized_email
            customer.phone = normalized_phone
            self._session.flush()
            return customer

        customer = Customer(
            full_name=request.full_name.strip(),
            email=normalized_email,
            phone=normalized_phone,
        )
        self._session.add(customer)
        self._session.flush()
        return customer

    def _find_existing_customer(self, *, email: str | None, phone: str | None) -> Customer | None:
        if email:
            statement = select(Customer).where(func.lower(Customer.email) == email)
            customer = self._session.scalars(statement).first()
            if customer is not None:
                return customer
        if phone:
            statement = select(Customer).where(Customer.phone == phone)
            return self._session.scalars(statement).first()
        return None

    def _release_expired_holds(self, now: datetime) -> None:
        statement = select(Appointment).where(
            Appointment.status == AppointmentStatus.HELD.value,
            Appointment.hold_expires_at <= now,
        )
        expired_holds = self._session.scalars(statement).all()
        for appointment in expired_holds:
            appointment.status = AppointmentStatus.CANCELLED.value
            appointment.hold_expires_at = None
            appointment.active_slot_key = None
        if expired_holds:
            self._session.flush()


def _active_slot_key(technician_id: int, scheduled_start: datetime) -> str:
    return f"{technician_id}:{_to_utc_minute(scheduled_start).isoformat()}"


def _confirmation_code() -> str:
    return f"SHS-{token_hex(4).upper()}"


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_utc_minute(value: datetime) -> datetime:
    return _to_utc(value).replace(second=0, microsecond=0)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
