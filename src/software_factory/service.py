from __future__ import annotations

from uuid import uuid4

from .agents import (
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
from .contracts import FactoryRun, ProjectRequest
from .model_gateway import FixtureModelGateway, NvidiaNimGateway, StructuredModel
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

    async def run(self, request: ProjectRequest) -> FactoryRun:
        project_id = uuid4()
        self.run_store.start_run(project_id, request.request)
        try:
            state = await self.workflow.ainvoke(
                {
                    "project_id": str(project_id),
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
            self.run_store.complete_run(result)
            return result
        except Exception as exc:
            self.run_store.fail_run(project_id, str(exc))
            raise
