"""Diagnostic conversation HTTP routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.exceptions import DiagnosticSessionNotFoundError
from app.schemas import (
    AgentToolCallRead,
    DiagnosticSessionCreate,
    DiagnosticSessionListResponse,
    DiagnosticSessionRead,
    DiagnosticTurnRequest,
    DiagnosticTurnResponse,
)
from app.services.diagnostics import DiagnosticService

router = APIRouter(tags=["diagnostics"])


@router.post(
    "/diagnostics/sessions",
    response_model=DiagnosticSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_diagnostic_session(
    request: DiagnosticSessionCreate,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiagnosticSessionRead:
    service = DiagnosticService(session, settings)
    return DiagnosticSessionRead.model_validate(service.create_session(request))


@router.get("/diagnostics/sessions", response_model=DiagnosticSessionListResponse)
def list_diagnostic_sessions(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiagnosticSessionListResponse:
    service = DiagnosticService(session, settings)
    return DiagnosticSessionListResponse(
        sessions=[
            DiagnosticSessionRead.model_validate(diagnostic_session)
            for diagnostic_session in service.list_sessions()
        ]
    )


@router.get("/diagnostics/sessions/{session_id}", response_model=DiagnosticSessionRead)
def get_diagnostic_session(
    session_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiagnosticSessionRead:
    service = DiagnosticService(session, settings)
    try:
        diagnostic_session = service.get_session(session_id)
    except DiagnosticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DiagnosticSessionRead.model_validate(diagnostic_session)


@router.post("/diagnostics/sessions/{session_id}/turn", response_model=DiagnosticTurnResponse)
def process_diagnostic_turn(
    session_id: int,
    request: DiagnosticTurnRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiagnosticTurnResponse:
    service = DiagnosticService(session, settings)
    try:
        result = service.process_turn(session_id=session_id, message=request.message)
        diagnostic_session = service.get_session(session_id)
    except DiagnosticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DiagnosticTurnResponse(
        session=DiagnosticSessionRead.model_validate(diagnostic_session),
        assistant_message=result.assistant_message,
        tool_calls=[
            AgentToolCallRead(name=tool_call.name.value, arguments=tool_call.arguments)
            for tool_call in result.tool_calls
        ],
    )
