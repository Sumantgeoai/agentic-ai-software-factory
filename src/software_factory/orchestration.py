from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypedDict

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
from .artifacts import ReleaseManager, assemble_artifacts
from .contracts import (
    ArchitectureSpec,
    ArtifactSet,
    CodeBundle,
    ExecutionEvidence,
    ProjectRequest,
    QualityReport,
    ReleaseArtifact,
    RequirementSpec,
    ReviewDecision,
    SecurityReport,
    TaskPlan,
)
from .persistence import DatabaseRunStore
from .runtime import WorkspaceRuntime
from .security import SecurityAgent


class WorkflowState(TypedDict, total=False):
    project_id: str
    request: ProjectRequest
    requirements: RequirementSpec
    architecture: ArchitectureSpec
    plan: TaskPlan
    database_artifacts: ArtifactSet
    backend_artifacts: ArtifactSet
    frontend_artifacts: ArtifactSet
    qa_artifacts: ArtifactSet
    devops_artifacts: ArtifactSet
    bundle: CodeBundle
    security: SecurityReport
    execution: ExecutionEvidence
    quality: QualityReport
    review: ReviewDecision
    release: ReleaseArtifact
    repair_attempts: int
    max_repair_attempts: int


class WorkflowNodes:
    def __init__(
        self,
        *,
        product_owner: ProductOwnerAgent,
        architect: SolutionArchitectAgent,
        planner: PlannerAgent,
        database: DatabaseAgent,
        backend: BackendAgent,
        frontend: FrontendAgent,
        qa: QAAgent,
        devops: DevOpsAgent,
        quality_gate: QualityGate,
        security: SecurityAgent,
        reviewer: ReviewerAgent,
        runtime: WorkspaceRuntime,
        release_manager: ReleaseManager,
        run_store: DatabaseRunStore,
    ) -> None:
        self.product_owner = product_owner
        self.architect = architect
        self.planner = planner
        self.database = database
        self.backend = backend
        self.frontend = frontend
        self.qa = qa
        self.devops = devops
        self.quality_gate = quality_gate
        self.security = security
        self.reviewer = reviewer
        self.runtime = runtime
        self.release_manager = release_manager
        self.run_store = run_store

    def _audit(
        self,
        state: WorkflowState,
        actor: str,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.run_store.append_event(state["project_id"], actor, event_type, payload or {})

    async def product_owner_node(self, state: WorkflowState) -> dict[str, Any]:
        requirements = await self.product_owner.run(state["request"])
        self._audit(
            state,
            "product_owner",
            "requirements.completed",
            {"acceptance_criteria": len(requirements.acceptance_criteria)},
        )
        return {"requirements": requirements}

    async def architect_node(self, state: WorkflowState) -> dict[str, Any]:
        architecture = await self.architect.run(state["request"], state["requirements"])
        self._audit(
            state,
            "architect",
            "architecture.completed",
            {"services": len(architecture.services)},
        )
        return {"architecture": architecture}

    async def planner_node(self, state: WorkflowState) -> dict[str, Any]:
        plan = await self.planner.run(state["requirements"], state["architecture"])
        self._audit(state, "planner", "plan.completed", {"task_count": len(plan.items)})
        return {"plan": plan}

    async def database_node(self, state: WorkflowState) -> dict[str, Any]:
        artifacts = await self.database.run(
            state["requirements"], state["architecture"], state["plan"]
        )
        self._audit(state, "database", "artifacts.completed", {"files": len(artifacts.files)})
        return {"database_artifacts": artifacts}

    async def backend_node(self, state: WorkflowState) -> dict[str, Any]:
        artifacts = await self.backend.run(
            state["requirements"], state["architecture"], state["plan"]
        )
        self._audit(state, "backend", "artifacts.completed", {"files": len(artifacts.files)})
        return {"backend_artifacts": artifacts}

    async def frontend_node(self, state: WorkflowState) -> dict[str, Any]:
        artifacts = await self.frontend.run(
            state["requirements"], state["architecture"], state["plan"]
        )
        self._audit(state, "frontend", "artifacts.completed", {"files": len(artifacts.files)})
        return {"frontend_artifacts": artifacts}

    async def qa_artifacts_node(self, state: WorkflowState) -> dict[str, Any]:
        artifacts = await self.qa.run(state["requirements"], state["architecture"], state["plan"])
        self._audit(state, "qa", "artifacts.completed", {"files": len(artifacts.files)})
        return {"qa_artifacts": artifacts}

    async def devops_node(self, state: WorkflowState) -> dict[str, Any]:
        artifacts = await self.devops.run(
            state["requirements"], state["architecture"], state["plan"]
        )
        self._audit(state, "devops", "artifacts.completed", {"files": len(artifacts.files)})
        return {"devops_artifacts": artifacts}

    async def assemble_node(self, state: WorkflowState) -> dict[str, Any]:
        bundle = assemble_artifacts(
            [
                state["database_artifacts"],
                state["backend_artifacts"],
                state["frontend_artifacts"],
                state["qa_artifacts"],
                state["devops_artifacts"],
            ]
        )
        self._audit(state, "orchestrator", "artifacts.assembled", {"files": len(bundle.files)})
        return {"bundle": bundle}

    async def security_node(self, state: WorkflowState) -> dict[str, Any]:
        report = await self.security.run(state["bundle"])
        self._audit(
            state,
            "security",
            "security.completed",
            {"passed": report.passed, "findings": len(report.findings)},
        )
        return {"security": report}

    @staticmethod
    def route_after_security(state: WorkflowState) -> Literal["execute", "security_block"]:
        return "execute" if state["security"].passed else "security_block"

    async def security_block_node(self, state: WorkflowState) -> dict[str, Any]:
        failures = [
            f"{item.severity}:{item.rule}:{item.file}: {item.message}"
            for item in state["security"].findings
        ]
        execution = ExecutionEvidence(
            workspace=str(self.runtime.policy.project_dir(state["project_id"])),
            files_written=[],
            commands=[],
        )
        quality = QualityReport(
            passed=False,
            summary="Execution blocked by the deterministic security gate.",
            failures=failures,
        )
        return {"execution": execution, "quality": quality}

    async def execute_node(self, state: WorkflowState) -> dict[str, Any]:
        execution = await self.runtime.materialize(
            state["project_id"],
            state["bundle"],
            generation=state.get("repair_attempts", 0),
        )
        self._audit(
            state,
            "runtime",
            "validation.executed",
            {"files": len(execution.files_written), "commands": len(execution.commands)},
        )
        return {"execution": execution}

    async def quality_node(self, state: WorkflowState) -> dict[str, Any]:
        quality = await self.quality_gate.run(state["execution"])
        self._audit(state, "qa", "quality.completed", {"passed": quality.passed})
        return {"quality": quality}

    async def repair_node(self, state: WorkflowState) -> dict[str, Any]:
        failure = next(command for command in state["execution"].commands if not command.passed)
        bundle = await self.backend.repair(
            state["requirements"],
            state["architecture"],
            state["plan"],
            state["bundle"],
            failure,
        )
        attempts = state.get("repair_attempts", 0) + 1
        self._audit(state, "backend", "repair.completed", {"attempt": attempts})
        return {"bundle": bundle, "repair_attempts": attempts}

    async def review_node(self, state: WorkflowState) -> dict[str, Any]:
        review = await self.reviewer.run(state["quality"], state["security"])
        self._audit(state, "reviewer", "review.completed", {"approved": review.approved})
        return {"review": review}

    async def release_node(self, state: WorkflowState) -> dict[str, Any]:
        release = self.release_manager.create(
            Path(state["execution"].workspace), state["execution"].files_written
        )
        self._audit(
            state,
            "release",
            "release.created",
            {"sha256": release.sha256, "file_count": release.file_count},
        )
        return {"release": release}

    @staticmethod
    def route_after_qa(state: WorkflowState) -> Literal["repair", "review"]:
        if state["quality"].passed:
            return "review"
        if state.get("repair_attempts", 0) < state["max_repair_attempts"]:
            return "repair"
        return "review"

    @staticmethod
    def route_after_review(state: WorkflowState) -> Literal["release", "end"]:
        return "release" if state["review"].approved else "end"


class SequentialWorkflow:
    def __init__(self, nodes: WorkflowNodes) -> None:
        self.nodes = nodes

    async def ainvoke(self, state: WorkflowState) -> WorkflowState:
        current = dict(state)
        for node in (
            self.nodes.product_owner_node,
            self.nodes.architect_node,
            self.nodes.planner_node,
            self.nodes.database_node,
            self.nodes.backend_node,
            self.nodes.frontend_node,
            self.nodes.qa_artifacts_node,
            self.nodes.devops_node,
            self.nodes.assemble_node,
        ):
            current.update(await node(current))

        while True:
            current.update(await self.nodes.security_node(current))
            if self.nodes.route_after_security(current) == "security_block":
                current.update(await self.nodes.security_block_node(current))
                break
            current.update(await self.nodes.execute_node(current))
            current.update(await self.nodes.quality_node(current))
            if self.nodes.route_after_qa(current) == "review":
                break
            current.update(await self.nodes.repair_node(current))

        current.update(await self.nodes.review_node(current))
        if self.nodes.route_after_review(current) == "release":
            current.update(await self.nodes.release_node(current))
        return current  # type: ignore[return-value]


def build_workflow(nodes: WorkflowNodes):  # type: ignore[no-untyped-def]
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return SequentialWorkflow(nodes)

    builder = StateGraph(WorkflowState)
    for name, node in (
        ("product_owner", nodes.product_owner_node),
        ("architect", nodes.architect_node),
        ("planner", nodes.planner_node),
        ("database", nodes.database_node),
        ("backend", nodes.backend_node),
        ("frontend", nodes.frontend_node),
        ("qa_artifacts", nodes.qa_artifacts_node),
        ("devops", nodes.devops_node),
        ("assemble", nodes.assemble_node),
        ("security", nodes.security_node),
        ("security_block", nodes.security_block_node),
        ("execute", nodes.execute_node),
        ("quality", nodes.quality_node),
        ("repair", nodes.repair_node),
        ("review", nodes.review_node),
        ("release", nodes.release_node),
    ):
        builder.add_node(name, node)
    builder.add_edge(START, "product_owner")
    builder.add_edge("product_owner", "architect")
    builder.add_edge("architect", "planner")
    builder.add_edge("planner", "database")
    builder.add_edge("database", "backend")
    builder.add_edge("backend", "frontend")
    builder.add_edge("frontend", "qa_artifacts")
    builder.add_edge("qa_artifacts", "devops")
    builder.add_edge("devops", "assemble")
    builder.add_edge("assemble", "security")
    builder.add_conditional_edges(
        "security",
        nodes.route_after_security,
        {"execute": "execute", "security_block": "security_block"},
    )
    builder.add_edge("security_block", "review")
    builder.add_edge("execute", "quality")
    builder.add_conditional_edges(
        "quality",
        nodes.route_after_qa,
        {"repair": "repair", "review": "review"},
    )
    builder.add_edge("repair", "security")
    builder.add_conditional_edges(
        "review",
        nodes.route_after_review,
        {"release": "release", "end": END},
    )
    builder.add_edge("release", END)
    return builder.compile()
