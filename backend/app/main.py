"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.diagnostics import router as diagnostics_router
from app.api.scheduling import router as scheduling_router
from app.api.twilio_voice import router as twilio_voice_router
from app.api.uploads import router as uploads_router
from app.config import Settings, get_settings
from app.schemas import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    app = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.get("/healthz", response_model=HealthResponse, tags=["health"])
    def healthz() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="shs-ai-agent-backend",
            environment=runtime_settings.environment,
        )

    app.include_router(diagnostics_router)
    app.include_router(scheduling_router)
    app.include_router(twilio_voice_router)
    app.include_router(uploads_router)
    return app


app = create_app()
