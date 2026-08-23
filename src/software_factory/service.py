from __future__ import annotations

from uuid import uuid4

from .agents import (
    BackendAgent,
    PlannerAgent,
    ProductOwnerAgent,
    QAAgent,
    ReviewerAgent,
    SolutionArchitectAgent,
)
from .config import Settings
from .contracts import FactoryRun, ProjectRequest
from .model_gateway import FixtureModelGateway, NvidiaNimGateway, StructuredModel
from .orchestration import WorkflowNodes, build_workflow
from .runtime import WorkspacePolicy, WorkspaceRuntime


class SoftwareFactoryService:
    def __init__(self, settings: Settings, model: StructuredModel | None = None) -> None:
        self.settings = settings
        self.model = model or self._create_model(settings)
        runtime = WorkspaceRuntime(
            WorkspacePolicy(
                settings.workspace_root, timeout_seconds=settings.command_timeout_seconds
            )
        )
        self.nodes = WorkflowNodes(
            product_owner=ProductOwnerAgent(self.model),
            architect=SolutionArchitectAgent(self.model),
            planner=PlannerAgent(self.model),
            backend=BackendAgent(self.model),
            qa=QAAgent(),
            reviewer=ReviewerAgent(),
            runtime=runtime,
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
        state = await self.workflow.ainvoke(
            {
                "project_id": str(project_id),
                "request": request,
                "repair_attempts": 0,
                "max_repair_attempts": self.settings.max_repair_attempts,
            }
        )
        return FactoryRun(
            project_id=project_id,
            requirements=state["requirements"],
            architecture=state["architecture"],
            plan=state["plan"],
            execution=state["execution"],
            quality=state["quality"],
            review=state["review"],
            repair_attempts=state.get("repair_attempts", 0),
        )
