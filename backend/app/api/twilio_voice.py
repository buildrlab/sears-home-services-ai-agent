"""Twilio voice HTTP and WebSocket routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.services.twilio_voice import (
    TwilioVoiceService,
    conversation_relay_twiml,
    gather_twiml,
    parse_twilio_form,
    parse_websocket_payload,
    validate_twilio_signature,
    validate_twilio_websocket_signature,
    websocket_setup_ack,
    websocket_text_response,
)

router = APIRouter(tags=["twilio"])


@router.post("/twilio/voice/incoming")
async def incoming_voice(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    params = await parse_twilio_form(request)
    validate_twilio_signature(request, params, settings)
    service = TwilioVoiceService(session, settings)
    call_session = service.create_or_get_call_session(params)
    service.record_event(call_session, event_type="voice_incoming", payload=params)

    if settings.twilio_voice_mode == "conversationrelay":
        twiml = conversation_relay_twiml(websocket_url=settings.twilio_conversation_relay_url)
    else:
        twiml = gather_twiml(
            prompt="Thanks for calling Sears Home Services. Which appliance needs help today?",
            action_url="/twilio/voice/gather",
        )
    return Response(content=twiml, media_type="application/xml")


@router.post("/twilio/voice/gather")
async def gather_response(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    params = await parse_twilio_form(request)
    validate_twilio_signature(request, params, settings)
    service = TwilioVoiceService(session, settings)
    call_session = service.create_or_get_call_session(params)
    service.record_event(call_session, event_type="gather_response", payload=params)
    speech = params.get("SpeechResult") or ""
    prompt = service.process_speech(call_session, speech) if speech else "Please repeat that."
    return Response(
        content=gather_twiml(prompt=prompt, action_url="/twilio/voice/gather"),
        media_type="application/xml",
    )


@router.post("/twilio/voice/status", status_code=status.HTTP_204_NO_CONTENT)
async def status_callback(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    params = await parse_twilio_form(request)
    validate_twilio_signature(request, params, settings)
    service = TwilioVoiceService(session, settings)
    call_session = service.create_or_get_call_session(params)
    service.record_event(call_session, event_type="status_callback", payload=params)
    service.mark_status(call_session, params.get("CallStatus"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.websocket("/twilio/conversation")
async def conversation_relay(
    websocket: WebSocket,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    validate_twilio_websocket_signature(websocket, settings)
    await websocket.accept()
    service = TwilioVoiceService(session, settings)
    call_sid: str | None = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = parse_websocket_payload(raw)
            except ValueError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
                continue

            event_type = str(payload.get("type") or payload.get("event") or "")
            if event_type == "setup":
                call_sid = str(payload.get("callSid") or payload.get("call_sid") or "local-call")
                call_session = service.create_or_get_call_session({"CallSid": call_sid})
                service.record_event(call_session, event_type="conversation_setup", payload=payload)
                session.commit()
                await websocket.send_json(websocket_setup_ack(call_sid))
                continue

            if event_type in {"prompt", "text"}:
                text = str(payload.get("text") or payload.get("prompt") or "")
                call_session = service.create_or_get_call_session(
                    {"CallSid": call_sid or "local-call"}
                )
                service.record_event(
                    call_session,
                    event_type="conversation_prompt",
                    payload=payload,
                )
                response_text = (
                    service.process_speech(call_session, text) if text else "Please repeat that."
                )
                session.commit()
                await websocket.send_json(websocket_text_response(response_text))
                continue

            await websocket.send_json({"type": "error", "message": "Unsupported event."})
    except WebSocketDisconnect:
        return
