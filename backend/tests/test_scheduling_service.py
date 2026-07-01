from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine

from app.database import create_session_factory
from app.exceptions import InvalidSchedulingRequestError, SlotUnavailableError
from app.models import Appointment, AppointmentStatus, Customer
from app.schemas import AppointmentHoldRequest, CustomerCreate
from app.seed import seed_reference_data
from app.services.scheduling import SchedulingService


def _hold_request(
    *,
    technician_id: int = 1,
    scheduled_start: datetime | None = None,
    zip_code: str = "75201",
    appliance_type: str = "refrigerator",
) -> AppointmentHoldRequest:
    return AppointmentHoldRequest(
        customer=CustomerCreate(
            full_name="Jordan Customer",
            email="jordan.customer@example.test",
            phone="+15551234567",
        ),
        technician_id=technician_id,
        appliance_type=appliance_type,
        zip_code=zip_code,
        scheduled_start=scheduled_start or datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
        issue_summary="Refrigerator is not cooling.",
    )


def _seed(session) -> None:
    seed_reference_data(session)
    session.commit()


def test_scheduling_service_creates_hold_and_books_confirmation(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)

    hold = service.create_hold(_hold_request())
    db_session.commit()
    booked = service.book_appointment(hold.id)
    db_session.commit()

    persisted = service.get_appointment(booked.id)
    assert persisted.status == AppointmentStatus.BOOKED.value
    assert persisted.confirmation_code is not None
    assert persisted.confirmation_code.startswith("SHS-")
    assert persisted.customer.email == "jordan.customer@example.test"
    assert persisted.technician.name == "Avery Johnson"


def test_scheduling_service_booking_is_idempotent_once_confirmed(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)
    hold = service.create_hold(_hold_request())
    booked = service.book_appointment(hold.id)
    first_confirmation = booked.confirmation_code

    booked_again = service.book_appointment(hold.id)

    assert booked_again.status == AppointmentStatus.BOOKED.value
    assert booked_again.confirmation_code == first_confirmation


def test_scheduling_service_creates_first_available_hold_from_preference(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)

    hold = service.create_first_available_hold(
        zip_code="75201",
        appliance_type="refrigerator",
        customer=CustomerCreate(
            full_name="Voice Caller",
            email=None,
            phone="+15551234567",
        ),
        issue_summary="Voice diagnostic for refrigerator: not cooling.",
        availability_preference="Monday morning works for me.",
        now=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
    )

    assert hold.status == AppointmentStatus.HELD.value
    assert hold.technician.name == "Avery Johnson"
    assert hold.scheduled_start == datetime(2026, 7, 6, 8, 0, tzinfo=UTC)


def test_scheduling_service_rejects_first_available_when_preference_has_no_slot(
    db_session,
) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)

    with pytest.raises(SlotUnavailableError, match="No matching technician time slot"):
        service.create_first_available_hold(
            zip_code="75201",
            appliance_type="refrigerator",
            customer=CustomerCreate(full_name="Voice Caller", phone="+15551234567"),
            issue_summary="Voice diagnostic for refrigerator: not cooling.",
            availability_preference="Sunday afternoon only.",
            now=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        )


def test_scheduling_service_rejects_unsupported_zip(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)

    with pytest.raises(InvalidSchedulingRequestError, match="ZIP code"):
        service.create_hold(_hold_request(zip_code="99999"))


def test_scheduling_service_rejects_unsupported_appliance(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)

    with pytest.raises(InvalidSchedulingRequestError, match="appliance"):
        service.create_hold(_hold_request(appliance_type="oven"))


def test_scheduling_service_rejects_unavailable_time(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)

    with pytest.raises(InvalidSchedulingRequestError, match="not available"):
        service.create_hold(_hold_request(scheduled_start=datetime(2026, 7, 6, 17, 0, tzinfo=UTC)))


def test_scheduling_service_rejects_cross_day_appointment_window(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)
    request = _hold_request(scheduled_start=datetime(2026, 7, 6, 23, 30, tzinfo=UTC))
    request.duration_minutes = 120

    with pytest.raises(InvalidSchedulingRequestError, match="within one availability day"):
        service.create_hold(request)


def test_scheduling_service_prevents_double_booking(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)
    service.create_hold(_hold_request())
    db_session.commit()

    with pytest.raises(SlotUnavailableError):
        service.create_hold(
            _hold_request(
                # Use a second customer so this test only exercises slot uniqueness.
                scheduled_start=datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
            )
        )


def test_scheduling_service_expires_hold_before_booking(db_session, monkeypatch) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)
    hold = service.create_hold(_hold_request())
    hold.hold_expires_at = datetime(2020, 1, 1, tzinfo=UTC)
    db_session.flush()
    monkeypatch.setattr(service, "_release_expired_holds", lambda now: None)

    with pytest.raises(SlotUnavailableError, match="hold has expired"):
        service.book_appointment(hold.id)

    expired = service.get_appointment(hold.id)
    assert expired.status == AppointmentStatus.CANCELLED.value
    assert expired.active_slot_key is None


def test_scheduling_service_rejects_booking_cancelled_appointment(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)
    hold = service.create_hold(_hold_request())
    cancelled = service.cancel_appointment(hold.id)

    with pytest.raises(InvalidSchedulingRequestError, match="Only held appointments"):
        service.book_appointment(cancelled.id)


def test_cancelled_appointment_releases_slot(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)
    hold = service.create_hold(_hold_request())
    db_session.commit()

    cancelled = service.cancel_appointment(hold.id)
    db_session.commit()
    second_hold = service.create_hold(_hold_request())
    db_session.commit()

    assert cancelled.status == AppointmentStatus.CANCELLED.value
    assert second_hold.id != cancelled.id
    assert second_hold.status == AppointmentStatus.HELD.value


def test_scheduling_service_reuses_existing_customer_by_email(db_session) -> None:
    _seed(db_session)
    service = SchedulingService(db_session)
    first_hold = service.create_hold(_hold_request())
    db_session.commit()
    request = _hold_request(
        scheduled_start=datetime(2026, 7, 8, 13, 0, tzinfo=UTC),
        technician_id=1,
    )
    request.customer.full_name = "Updated Customer"
    request.customer.email = "JORDAN.CUSTOMER@EXAMPLE.TEST"
    request.customer.phone = "+15557654321"

    second_hold = service.create_hold(request)

    customers = db_session.query(Customer).all()
    assert len(customers) == 1
    assert second_hold.customer_id == first_hold.customer_id
    assert second_hold.customer.full_name == "Updated Customer"
    assert second_hold.customer.email == "jordan.customer@example.test"


def test_concurrent_holds_allow_only_one_winner(sqlite_engine: Engine) -> None:
    session_factory = create_session_factory(sqlite_engine)
    with session_factory() as session:
        _seed(session)

    def attempt_hold(index: int) -> str:
        with session_factory() as session:
            service = SchedulingService(session)
            try:
                request = _hold_request()
                request.customer.email = f"race-{index}@example.test"
                appointment = service.create_hold(request)
                session.commit()
                return f"held:{appointment.id}"
            except SlotUnavailableError:
                session.rollback()
                return "unavailable"

    for worker_count in (2, 4, 8):
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            results = list(executor.map(attempt_hold, range(worker_count)))

        assert sum(result.startswith("held:") for result in results) == 1
        assert results.count("unavailable") == worker_count - 1

        with session_factory() as session:
            appointments = session.query(Appointment).all()
            for appointment in appointments:
                appointment.status = AppointmentStatus.CANCELLED.value
                appointment.active_slot_key = None
            session.commit()
