from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .contracts import FactoryRun, ProjectRequest
from .service import SoftwareFactoryService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Agentic AI Software Factory", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
    )
    app.state.factory = SoftwareFactoryService(settings)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "model_provider": settings.model_provider}

    @app.post("/api/v1/projects/run", response_model=FactoryRun)
    async def run_project(payload: ProjectRequest, request: Request) -> FactoryRun:
        try:
            return await request.app.state.factory.run(payload)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app
