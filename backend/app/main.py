"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.scheduling import router as scheduling_router
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

    @app.get("/healthz", response_model=HealthResponse, tags=["health"])
    def healthz() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="shs-ai-agent-backend",
            environment=runtime_settings.environment,
        )

    app.include_router(scheduling_router)
    return app


app = create_app()
