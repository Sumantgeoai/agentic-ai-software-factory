from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from .contracts import (
    AgentRole,
    ArchitectureSpec,
    ArtifactSet,
    CodeBundle,
    RequirementSpec,
    TargetProfile,
    TaskPlan,
    WorkItem,
)
from .lightweight_fixture import FixtureModelGateway
from .scenario_fixtures import ScenarioFixture, scenario_for_request
from .spec_runtime_compiler import (
    render_enterprise_role_artifacts,
    render_enterprise_runtime_bundle,
)
from .specification import ApplicationSpec

T = TypeVar("T", bound=BaseModel)


class SpecDrivenFixtureModelGateway(FixtureModelGateway):
    """Deterministic multi-domain enterprise fixture built from ApplicationSpec."""

    async def complete(self, schema: type[T], *, system: str, user: str) -> T:
        enterprise = TargetProfile.ENTERPRISE_DOTNET_REACT.value in user
        if not enterprise:
            return await super().complete(schema, system=system, user=user)

        scenario = scenario_for_request(user)
        if schema is RequirementSpec:
            value: BaseModel = scenario.requirements
        elif schema is ArchitectureSpec:
            value = _architecture(scenario)
        elif schema is ApplicationSpec:
            value = scenario.application_spec
        elif schema is TaskPlan:
            value = _task_plan(scenario)
        elif schema is ArtifactSet:
            value = _artifact_set(scenario, system)
        elif schema is CodeBundle:
            value = render_enterprise_runtime_bundle(
                scenario.requirements,
                scenario.application_spec,
            )
        else:
            raise TypeError(f"Spec-driven fixture does not support {schema.__name__}")
        return schema.model_validate(value.model_dump())


def _architecture(scenario: ScenarioFixture) -> ArchitectureSpec:
    name = scenario.requirements.product_name
    return ArchitectureSpec(
        summary=(
            f"Modular ASP.NET Core application for {name} with backend authorization, "
            "React/TypeScript UI and PostgreSQL persistence."
        ),
        backend="ASP.NET Core Web API / .NET 10",
        frontend="React 19 + TypeScript 7 + React Router 7 + Vite 8",
        database="PostgreSQL 16 with EF Core 10/Npgsql",
        authentication="OIDC/JWT bearer authentication with backend role policies",
        services=["api", "web", "postgres"],
        security_constraints=[
            "Backend authorization is authoritative; frontend visibility is UX only",
            "Business-rule enforcement is generated from the validated ApplicationSpec",
            "Row-level own/team/all scopes are generated from typed claim bindings",
            "Generated files remain inside the governed workspace runtime",
        ],
        decisions=[
            "Use the validated ApplicationSpec as the only domain source of truth",
            "Compile enterprise source deterministically after probabilistic specification",
            "Fail closed when a typed business rule or scope binding is unsupported",
        ],
    )


def _task_plan(scenario: ScenarioFixture) -> TaskPlan:
    name = scenario.requirements.product_name
    return TaskPlan(
        items=[
            WorkItem(
                id="DB-1",
                title=f"Generate PostgreSQL persistence for {name}",
                owner=AgentRole.DATABASE,
                acceptance_criteria=["Entity schema and EF migration derive from ApplicationSpec"],
            ),
            WorkItem(
                id="API-1",
                title=f"Generate secured ASP.NET Core API for {name}",
                owner=AgentRole.BACKEND,
                depends_on=["DB-1"],
                acceptance_criteria=[
                    "Role policies, row scopes and backend business rules derive from ApplicationSpec"
                ],
            ),
            WorkItem(
                id="UI-1",
                title=f"Generate role-aware React application for {name}",
                owner=AgentRole.FRONTEND,
                depends_on=["API-1"],
                acceptance_criteria=["Routes and navigation derive from ApplicationSpec"],
            ),
            WorkItem(
                id="QA-1",
                title=f"Generate deterministic rule and scope tests for {name}",
                owner=AgentRole.QA,
                depends_on=["API-1", "UI-1"],
                acceptance_criteria=["Generated xUnit and contract tests validate the specification"],
            ),
            WorkItem(
                id="OPS-1",
                title=f"Package {name} for local integration",
                owner=AgentRole.DEVOPS,
                depends_on=["QA-1"],
                acceptance_criteria=["Docker assets externalize database and identity configuration"],
            ),
        ]
    )


def _artifact_set(scenario: ScenarioFixture, system: str) -> ArtifactSet:
    role = system.lower()
    roles = {
        "database specialist": AgentRole.DATABASE,
        "backend specialist": AgentRole.BACKEND,
        "frontend specialist": AgentRole.FRONTEND,
        "qa specialist": AgentRole.QA,
        "devops specialist": AgentRole.DEVOPS,
    }
    for marker, agent_role in roles.items():
        if marker in role:
            return render_enterprise_role_artifacts(
                agent_role,
                scenario.requirements,
                scenario.application_spec,
            )
    raise ValueError("Spec-driven fixture could not identify specialist role")
