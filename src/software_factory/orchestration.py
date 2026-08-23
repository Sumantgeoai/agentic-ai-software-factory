from __future__ import annotations

from typing import Any, Literal, TypedDict

from .agents import (
    BackendAgent,
    PlannerAgent,
    ProductOwnerAgent,
    QAAgent,
    ReviewerAgent,
    SolutionArchitectAgent,
)
from .contracts import (
    ArchitectureSpec,
    CodeBundle,
    ExecutionEvidence,
    ProjectRequest,
    QualityReport,
    RequirementSpec,
    ReviewDecision,
    TaskPlan,
)
from .runtime import WorkspaceRuntime


class WorkflowState(TypedDict, total=False):
    project_id: str
    request: ProjectRequest
    requirements: RequirementSpec
    architecture: ArchitectureSpec
    plan: TaskPlan
    bundle: CodeBundle
    execution: ExecutionEvidence
    quality: QualityReport
    review: ReviewDecision
    repair_attempts: int
    max_repair_attempts: int


class WorkflowNodes:
    def __init__(
        self,
        *,
        product_owner: ProductOwnerAgent,
        architect: SolutionArchitectAgent,
        planner: PlannerAgent,
        backend: BackendAgent,
        qa: QAAgent,
        reviewer: ReviewerAgent,
        runtime: WorkspaceRuntime,
    ) -> None:
        self.product_owner = product_owner
        self.architect = architect
        self.planner = planner
        self.backend = backend
        self.qa = qa
        self.reviewer = reviewer
        self.runtime = runtime

    async def product_owner_node(self, state: WorkflowState) -> dict[str, Any]:
        return {"requirements": await self.product_owner.run(state["request"])}

    async def architect_node(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "architecture": await self.architect.run(state["request"], state["requirements"])
        }

    async def planner_node(self, state: WorkflowState) -> dict[str, Any]:
        return {"plan": await self.planner.run(state["requirements"], state["architecture"])}

    async def backend_node(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "bundle": await self.backend.run(
                state["requirements"], state["architecture"], state["plan"]
            )
        }

    async def execute_node(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "execution": await self.runtime.materialize(
                state["project_id"],
                state["bundle"],
                generation=state.get("repair_attempts", 0),
            )
        }

    async def qa_node(self, state: WorkflowState) -> dict[str, Any]:
        return {"quality": await self.qa.run(state["execution"])}

    async def repair_node(self, state: WorkflowState) -> dict[str, Any]:
        failure = next(command for command in state["execution"].commands if not command.passed)
        bundle = await self.backend.repair(
            state["requirements"],
            state["architecture"],
            state["plan"],
            state["bundle"],
            failure,
        )
        return {"bundle": bundle, "repair_attempts": state.get("repair_attempts", 0) + 1}

    async def review_node(self, state: WorkflowState) -> dict[str, Any]:
        return {"review": await self.reviewer.run(state["quality"])}

    @staticmethod
    def route_after_qa(state: WorkflowState) -> Literal["repair", "review"]:
        if state["quality"].passed:
            return "review"
        if state.get("repair_attempts", 0) < state["max_repair_attempts"]:
            return "repair"
        return "review"


class SequentialWorkflow:
    def __init__(self, nodes: WorkflowNodes) -> None:
        self.nodes = nodes

    async def ainvoke(self, state: WorkflowState) -> WorkflowState:
        current = dict(state)
        for node in (
            self.nodes.product_owner_node,
            self.nodes.architect_node,
            self.nodes.planner_node,
            self.nodes.backend_node,
        ):
            current.update(await node(current))

        while True:
            current.update(await self.nodes.execute_node(current))
            current.update(await self.nodes.qa_node(current))
            if self.nodes.route_after_qa(current) == "review":
                break
            current.update(await self.nodes.repair_node(current))

        current.update(await self.nodes.review_node(current))
        return current  # type: ignore[return-value]


def build_workflow(nodes: WorkflowNodes):  # type: ignore[no-untyped-def]
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return SequentialWorkflow(nodes)

    builder = StateGraph(WorkflowState)
    builder.add_node("product_owner", nodes.product_owner_node)
    builder.add_node("architect", nodes.architect_node)
    builder.add_node("planner", nodes.planner_node)
    builder.add_node("backend", nodes.backend_node)
    builder.add_node("execute", nodes.execute_node)
    builder.add_node("qa", nodes.qa_node)
    builder.add_node("repair", nodes.repair_node)
    builder.add_node("review", nodes.review_node)
    builder.add_edge(START, "product_owner")
    builder.add_edge("product_owner", "architect")
    builder.add_edge("architect", "planner")
    builder.add_edge("planner", "backend")
    builder.add_edge("backend", "execute")
    builder.add_edge("execute", "qa")
    builder.add_conditional_edges(
        "qa",
        nodes.route_after_qa,
        {"repair": "repair", "review": "review"},
    )
    builder.add_edge("repair", "execute")
    builder.add_edge("review", END)
    return builder.compile()
