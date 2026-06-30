"""Pydantic request and response schemas."""

from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import AppointmentStatus


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class TechnicianRead(BaseModel):
    id: int
    name: str
    email: str
    active: bool
    specialties: list[str]
    service_areas: list[str]

    model_config = ConfigDict(from_attributes=True)


class AvailabilityWindowRead(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    capacity: int = Field(ge=1)


class TechnicianMatchRead(BaseModel):
    id: int
    name: str
    email: str
    specialties: list[str]
    service_areas: list[str]
    availability: list[AvailabilityWindowRead]


class TechnicianMatchListResponse(BaseModel):
    matches: list[TechnicianMatchRead]


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def require_email_or_phone(self) -> CustomerCreate:
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required.")
        return self


class CustomerRead(BaseModel):
    id: int
    full_name: str
    email: str | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)


class TechnicianSummaryRead(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentHoldRequest(BaseModel):
    customer: CustomerCreate
    technician_id: int = Field(gt=0)
    appliance_type: str = Field(min_length=1, max_length=80)
    zip_code: str = Field(min_length=5, max_length=10)
    scheduled_start: datetime
    duration_minutes: int = Field(default=240, ge=30, le=480)
    hold_minutes: int = Field(default=15, ge=1, le=60)
    issue_summary: str | None = Field(default=None, max_length=1000)

    @field_validator("scheduled_start")
    @classmethod
    def scheduled_start_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_start must include a timezone offset.")
        return value


class AppointmentRead(BaseModel):
    id: int
    status: AppointmentStatus
    appliance_type: str
    zip_code: str
    issue_summary: str | None
    scheduled_start: datetime
    scheduled_end: datetime
    hold_expires_at: datetime | None
    confirmation_code: str | None
    customer: CustomerRead
    technician: TechnicianSummaryRead

    model_config = ConfigDict(from_attributes=True)


class AppointmentListResponse(BaseModel):
    appointments: list[AppointmentRead]
