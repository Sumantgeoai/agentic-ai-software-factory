from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from opentelemetry.trace import Status, StatusCode

from .agents import (
    ApplicationSpecificationAgent,
    BackendAgent,
    DatabaseAgent,
    DevOpsAgent,
    FrontendAgent,
    PlannerAgent,
    ProductOwnerAgent,
    QAAgent,
    QualityGate,
    ReviewerAgent,
    SolutionArchitectAgent,
)
from .artifacts import ReleaseManager
from .config import Settings
from .contracts import AuditEvent, FactoryRun, ProjectRequest, StoredRun
from .model_gateway import FixtureModelGateway, NvidiaNimGateway, StructuredModel
from .observability import current_correlation_id, get_tracer
from .orchestration import WorkflowNodes, build_workflow
from .persistence import DatabaseRunStore
from .runtime import WorkspacePolicy, WorkspaceRuntime
from .security import SecurityAgent


class SoftwareFactoryService:
    def __init__(self, settings: Settings, model: StructuredModel | None = None) -> None:
        self.settings = settings
        self.model = model or self._create_model(settings)
        self.run_store = DatabaseRunStore(settings.database_url)
        self.run_store.initialize()
        runtime = WorkspaceRuntime(
            WorkspacePolicy(
                settings.workspace_root, timeout_seconds=settings.command_timeout_seconds
            )
        )
        self.nodes = WorkflowNodes(
            product_owner=ProductOwnerAgent(self.model),
            architect=SolutionArchitectAgent(self.model),
            application_specification=ApplicationSpecificationAgent(self.model),
            planner=PlannerAgent(self.model),
            database=DatabaseAgent(self.model),
            backend=BackendAgent(self.model),
            frontend=FrontendAgent(self.model),
            qa=QAAgent(self.model),
            devops=DevOpsAgent(self.model),
            quality_gate=QualityGate(),
            security=SecurityAgent(),
            reviewer=ReviewerAgent(),
            runtime=runtime,
            release_manager=ReleaseManager(),
            run_store=self.run_store,
        )
        self.workflow = build_workflow(self.nodes)

    @staticmethod
    def _create_model(settings: Settings) -> StructuredModel:
        if settings.model_provider == "fixture":
            return FixtureModelGateway()
        if settings.model_provider == "nvidia":
            return NvidiaNimGateway(settings)
        raise ValueError(f"Unsupported model provider: {settings.model_provider}")

    async def run(
        self,
        request: ProjectRequest,
        *,
        correlation_id: str | None = None,
    ) -> FactoryRun:
        project_id = uuid4()
        correlation_id = correlation_id or current_correlation_id()
        await asyncio.to_thread(
            self.run_store.start_run,
            project_id,
            request.request,
            correlation_id,
        )
        tracer = get_tracer()
        with tracer.start_as_current_span("factory.run") as span:
            span.set_attribute("factory.project_id", str(project_id))
            span.set_attribute("factory.target_profile", request.target_profile.value)
            if correlation_id:
                span.set_attribute("factory.correlation_id", correlation_id)
            try:
                state = await self.workflow.ainvoke(
                    {
                        "project_id": str(project_id),
                        "correlation_id": correlation_id or "",
                        "request": request,
                        "repair_attempts": 0,
                        "max_repair_attempts": self.settings.max_repair_attempts,
                    }
                )
                result = FactoryRun(
                    project_id=project_id,
                    requirements=state["requirements"],
                    architecture=state["architecture"],
                    plan=state["plan"],
                    execution=state["execution"],
                    quality=state["quality"],
                    security=state["security"],
                    review=state["review"],
                    release=state.get("release"),
                    repair_attempts=state.get("repair_attempts", 0),
                )
                await asyncio.to_thread(self.run_store.complete_run, result, correlation_id)
                span.set_attribute("factory.review.approved", result.review.approved)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as exc:
                await asyncio.to_thread(
                    self.run_store.fail_run,
                    project_id,
                    str(exc),
                    correlation_id,
                )
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise

    async def get_run(self, project_id: UUID) -> StoredRun | None:
        return await asyncio.to_thread(self.run_store.get_run, project_id)

    async def list_audit_events(self, project_id: UUID) -> list[AuditEvent]:
        return await asyncio.to_thread(self.run_store.list_events, project_id)
