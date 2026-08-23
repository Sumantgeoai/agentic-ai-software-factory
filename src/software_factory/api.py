from __future__ import annotations

import re
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.trace import Status, StatusCode

from .config import Settings
from .contracts import AuditEvent, FactoryRun, ProjectRequest, StoredRun
from .observability import configure_observability, correlation_context, get_tracer
from .service import SoftwareFactoryService

_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_observability(settings)
    app = FastAPI(title="Agentic AI Software Factory", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )
    app.state.factory = SoftwareFactoryService(settings)
    tracer = get_tracer()

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        correlation_id = request.headers.get("X-Correlation-ID") or uuid4().hex
        if not _CORRELATION_ID.fullmatch(correlation_id):
            generated = uuid4().hex
            response = JSONResponse(
                status_code=400,
                content={"detail": "Invalid X-Correlation-ID header"},
            )
            response.headers["X-Correlation-ID"] = generated
            return response

        with correlation_context(correlation_id), tracer.start_as_current_span("http.request") as span:
            span.set_attribute("http.request.method", request.method)
            span.set_attribute("factory.correlation_id", correlation_id)
            try:
                response = await call_next(request)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            response.headers["X-Correlation-ID"] = correlation_id
            return response

    async def require_api_key(request: Request) -> None:
        expected = settings.api_key
        if expected is None:
            return
        supplied = request.headers.get("X-API-Key") or ""
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise HTTPException(
                status_code=401,
                detail="Invalid API credentials",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

    @router.post("/projects/run", response_model=FactoryRun)
    async def run_project(payload: ProjectRequest, request: Request) -> FactoryRun:
        try:
            return await request.app.state.factory.run(
                payload,
                correlation_id=request.headers.get("X-Correlation-ID"),
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Factory request could not be completed",
            ) from exc

    @router.get("/runs/{project_id}", response_model=StoredRun)
    async def get_run(project_id: UUID, request: Request) -> StoredRun:
        run = await request.app.state.factory.get_run(project_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @router.get("/runs/{project_id}/audit", response_model=list[AuditEvent])
    async def get_audit(project_id: UUID, request: Request) -> list[AuditEvent]:
        run = await request.app.state.factory.get_run(project_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return await request.app.state.factory.list_audit_events(project_id)

    app.include_router(router)
    return app
