"""Pydantic response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
