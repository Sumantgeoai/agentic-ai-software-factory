from __future__ import annotations

from .contracts import (
    ArchitectureSpec,
    CodeBundle,
    CommandEvidence,
    ExecutionEvidence,
    ProjectRequest,
    QualityReport,
    RequirementSpec,
    ReviewDecision,
    TaskPlan,
)
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
                "You are the solution architect. Design the smallest production-sensible "
                "architecture that satisfies the validated requirements and makes security "
                "boundaries explicit."
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

    async def repair(
        self,
        requirements: RequirementSpec,
        architecture: ArchitectureSpec,
        plan: TaskPlan,
        previous: CodeBundle,
        failure: CommandEvidence,
    ) -> CodeBundle:
        return await self._model.complete(
            CodeBundle,
            system=(
                "You are repairing a failed implementation. Use the deterministic build/test "
                "evidence as the source of truth. Return a complete corrected file bundle."
            ),
            user=(
                f"Requirements: {requirements.model_dump_json()}\n"
                f"Architecture: {architecture.model_dump_json()}\n"
                f"Plan: {plan.model_dump_json()}\n"
                f"Previous bundle: {previous.model_dump_json()}\n"
                f"Failure: {failure.model_dump_json()}"
            ),
        )


class QAAgent:
    async def run(self, execution: ExecutionEvidence) -> QualityReport:
        failures = [
            command.stderr or command.stdout or f"{command.command} failed"
            for command in execution.commands
            if not command.passed
        ]
        return QualityReport(
            passed=execution.passed,
            summary=(
                "Configured deterministic quality gates passed."
                if execution.passed
                else "One or more deterministic quality gates failed."
            ),
            failures=failures,
        )


class ReviewerAgent:
    async def run(self, quality: QualityReport) -> ReviewDecision:
        return ReviewDecision(
            approved=quality.passed,
            summary=(
                "Release candidate approved from verified quality evidence."
                if quality.passed
                else "Release candidate rejected after bounded repair attempts."
            ),
            risks=[] if quality.passed else quality.failures,
        )
