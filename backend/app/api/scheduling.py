"""Scheduling HTTP routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.exceptions import (
    AppointmentNotFoundError,
    InvalidSchedulingRequestError,
    SlotUnavailableError,
)
from app.models import AppointmentStatus
from app.repositories import TechnicianMatch
from app.schemas import (
    AppointmentHoldRequest,
    AppointmentListResponse,
    AppointmentRead,
    AvailabilityWindowRead,
    TechnicianMatchListResponse,
    TechnicianMatchRead,
)
from app.services.scheduling import SchedulingService

router = APIRouter(tags=["scheduling"])


@router.get("/scheduling/matches", response_model=TechnicianMatchListResponse)
def find_matches(
    zip_code: Annotated[str, Query(min_length=5, max_length=10)],
    appliance_type: Annotated[str, Query(min_length=1, max_length=80)],
    session: Annotated[Session, Depends(get_db_session)],
) -> TechnicianMatchListResponse:
    service = SchedulingService(session)
    return TechnicianMatchListResponse(
        matches=[_match_to_schema(match) for match in service.find_matches(
            zip_code=zip_code,
            appliance_type=appliance_type,
        )]
    )


@router.post(
    "/appointments/holds",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment_hold(
    request: AppointmentHoldRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> AppointmentRead:
    service = SchedulingService(session)
    try:
        appointment = service.create_hold(request)
    except InvalidSchedulingRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AppointmentRead.model_validate(appointment)


@router.post("/appointments/{appointment_id}/book", response_model=AppointmentRead)
def book_appointment(
    appointment_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> AppointmentRead:
    service = SchedulingService(session)
    try:
        appointment = service.book_appointment(appointment_id)
    except AppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidSchedulingRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AppointmentRead.model_validate(appointment)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment(
    appointment_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> AppointmentRead:
    service = SchedulingService(session)
    try:
        appointment = service.cancel_appointment(appointment_id)
    except AppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AppointmentRead.model_validate(appointment)


@router.get("/appointments/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> AppointmentRead:
    service = SchedulingService(session)
    try:
        appointment = service.get_appointment(appointment_id)
    except AppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AppointmentRead.model_validate(appointment)


@router.get("/appointments", response_model=AppointmentListResponse)
def list_appointments(
    session: Annotated[Session, Depends(get_db_session)],
    status_filter: Annotated[AppointmentStatus | None, Query(alias="status")] = None,
) -> AppointmentListResponse:
    service = SchedulingService(session)
    return AppointmentListResponse(
        appointments=[
            AppointmentRead.model_validate(appointment)
            for appointment in service.list_appointments(status=status_filter)
        ]
    )


def _match_to_schema(match: TechnicianMatch) -> TechnicianMatchRead:
    return TechnicianMatchRead(
        id=match.id,
        name=match.name,
        email=match.email,
        specialties=list(match.specialties),
        service_areas=list(match.service_areas),
        availability=[
            AvailabilityWindowRead(
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                capacity=slot.capacity,
            )
            for slot in match.availability
        ],
    )
