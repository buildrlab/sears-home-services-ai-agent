"""Domain exceptions translated by API routes."""

from __future__ import annotations


class SchedulingError(Exception):
    """Base class for scheduling failures."""


class AppointmentNotFoundError(SchedulingError):
    """Raised when an appointment cannot be found."""


class InvalidSchedulingRequestError(SchedulingError):
    """Raised when a request conflicts with technician capability or availability."""


class SlotUnavailableError(SchedulingError):
    """Raised when a requested appointment slot is already held or booked."""
