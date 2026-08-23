from __future__ import annotations

from .contracts import ArchitectureSpec, CodeBundle, ProjectRequest, RequirementSpec, TaskPlan
from .model_gateway import StructuredModel


class ProductOwnerAgent:
    def __init__(self, model: StructuredModel) -> None:
        self._model = model

    async def run(self, request: ProjectRequest) -> RequirementSpec:
        return await self._model.complete(
            RequirementSpec,
            system=(
                "You are the product owner. Convert the request into precise scope and measurable "
                "acceptance criteria. Do not invent integrations that the request does not need."
            ),
            user=request.request,
        )


class SolutionArchitectAgent:
    def __init__(self, model: StructuredModel) -> None:
        self._model = model

    async def run(
        self, request: ProjectRequest, requirements: RequirementSpec
    ) -> ArchitectureSpec:
        return await self._model.complete(
            ArchitectureSpec,
            system=(
                "You are the solution architect. Design the smallest production-sensible architecture "
                "that satisfies the validated requirements and makes security boundaries explicit."
            ),
            user=f"Request: {request.request}\nRequirements: {requirements.model_dump_json()}",
        )


class PlannerAgent:
    def __init__(self, model: StructuredModel) -> None:
        self._model = model

    async def run(
        self,
        requirements: RequirementSpec,
        architecture: ArchitectureSpec,
    ) -> TaskPlan:
        return await self._model.complete(
            TaskPlan,
            system=(
                "You are the delivery planner. Produce dependency-aware engineering tasks with "
                "verifiable acceptance criteria. Keep tasks coarse enough to avoid busywork."
            ),
            user=(
                f"Requirements: {requirements.model_dump_json()}\n"
                f"Architecture: {architecture.model_dump_json()}"
            ),
        )


class BackendAgent:
    def __init__(self, model: StructuredModel) -> None:
        self._model = model

    async def run(
        self,
        requirements: RequirementSpec,
        architecture: ArchitectureSpec,
        plan: TaskPlan,
    ) -> CodeBundle:
        return await self._model.complete(
            CodeBundle,
            system=(
                "You are the implementation agent. Return complete files for the assigned vertical "
                "slice. Keep code idiomatic, concise, testable and free of placeholder TODOs."
            ),
            user=(
                f"Requirements: {requirements.model_dump_json()}\n"
                f"Architecture: {architecture.model_dump_json()}\nPlan: {plan.model_dump_json()}"
            ),
        )
