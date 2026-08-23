from __future__ import annotations

from .contracts import (
    AgentRole,
    ArchitectureSpec,
    ArtifactSet,
    CodeBundle,
    CommandEvidence,
    ExecutionEvidence,
    ProjectRequest,
    QualityReport,
    RequirementSpec,
    ReviewDecision,
    SecurityReport,
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
                "verifiable acceptance criteria. Assign database, backend, frontend, QA and DevOps "
                "work explicitly when the architecture requires those concerns."
            ),
            user=(
                f"Requirements: {requirements.model_dump_json()}\n"
                f"Architecture: {architecture.model_dump_json()}"
            ),
        )


class SpecialistArtifactAgent:
    role: AgentRole

    def __init__(self, model: StructuredModel) -> None:
        self._model = model

    async def run(
        self,
        requirements: RequirementSpec,
        architecture: ArchitectureSpec,
        plan: TaskPlan,
    ) -> ArtifactSet:
        assigned = [item for item in plan.items if item.owner is self.role]
        if not assigned:
            return ArtifactSet()
        return await self._model.complete(
            ArtifactSet,
            system=(
                f"You are the {self.role.value} specialist. Produce only files owned by this role. "
                "Return complete production-sensible artifacts with no placeholder TODOs. Do not "
                "perform side effects; deterministic tooling will materialize and validate files."
            ),
            user=(
                f"Requirements: {requirements.model_dump_json()}\n"
                f"Architecture: {architecture.model_dump_json()}\n"
                f"Assigned tasks: {[item.model_dump(mode='json') for item in assigned]}"
            ),
        )


class DatabaseAgent(SpecialistArtifactAgent):
    role = AgentRole.DATABASE


class FrontendAgent(SpecialistArtifactAgent):
    role = AgentRole.FRONTEND


class DevOpsAgent(SpecialistArtifactAgent):
    role = AgentRole.DEVOPS


class QAAgent(SpecialistArtifactAgent):
    role = AgentRole.QA


class BackendAgent(SpecialistArtifactAgent):
    role = AgentRole.BACKEND

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
                "You are repairing a failed integrated implementation. Use deterministic "
                "build/test evidence as the source of truth. Return a complete corrected file "
                "bundle."
            ),
            user=(
                f"Requirements: {requirements.model_dump_json()}\n"
                f"Architecture: {architecture.model_dump_json()}\n"
                f"Plan: {plan.model_dump_json()}\n"
                f"Previous bundle: {previous.model_dump_json()}\n"
                f"Failure: {failure.model_dump_json()}"
            ),
        )


class QualityGate:
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
    async def run(self, quality: QualityReport, security: SecurityReport) -> ReviewDecision:
        security_risks = [
            f"{finding.severity}:{finding.rule}:{finding.file}: {finding.message}"
            for finding in security.findings
        ]
        approved = quality.passed and security.passed
        risks = [*quality.failures, *security_risks]
        return ReviewDecision(
            approved=approved,
            summary=(
                "Release candidate approved from deterministic quality and security evidence."
                if approved
                else "Release candidate rejected by deterministic quality or security evidence."
            ),
            risks=risks,
        )
