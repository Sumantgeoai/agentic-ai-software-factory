from __future__ import annotations

from typing import Any, TypedDict

from .agents import BackendAgent, PlannerAgent, ProductOwnerAgent, SolutionArchitectAgent
from .contracts import (
    ArchitectureSpec,
    CodeBundle,
    ExecutionEvidence,
    ProjectRequest,
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
    review: ReviewDecision


class WorkflowNodes:
    def __init__(
        self,
        *,
        product_owner: ProductOwnerAgent,
        architect: SolutionArchitectAgent,
        planner: PlannerAgent,
        backend: BackendAgent,
        runtime: WorkspaceRuntime,
    ) -> None:
        self.product_owner = product_owner
        self.architect = architect
        self.planner = planner
        self.backend = backend
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
            "execution": await self.runtime.materialize(state["project_id"], state["bundle"])
        }

    async def review_node(self, state: WorkflowState) -> dict[str, Any]:
        execution = state["execution"]
        if execution.passed:
            decision = ReviewDecision(
                approved=True,
                summary="Release candidate passed the configured deterministic quality gates.",
            )
        else:
            failed = next(command for command in execution.commands if not command.passed)
            decision = ReviewDecision(
                approved=False,
                summary=f"Release candidate failed validation command: {failed.command}.",
                risks=[failed.stderr or failed.stdout or "Validation command failed"],
            )
        return {"review": decision}


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
            self.nodes.execute_node,
            self.nodes.review_node,
        ):
            current.update(await node(current))
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
    builder.add_node("review", nodes.review_node)
    builder.add_edge(START, "product_owner")
    builder.add_edge("product_owner", "architect")
    builder.add_edge("architect", "planner")
    builder.add_edge("planner", "backend")
    builder.add_edge("backend", "execute")
    builder.add_edge("execute", "review")
    builder.add_edge("review", END)
    return builder.compile()
