from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from .contracts import (
    AgentRole,
    ArchitectureSpec,
    ArtifactSet,
    CodeBundle,
    GeneratedFile,
    RequirementSpec,
    TargetProfile,
    TaskPlan,
    WorkItem,
)
from .model_gateway import FixtureModelGateway
from .project_model import EnterpriseProjectModel
from .scenario_fixtures import ScenarioFixture, scenario_for_request
from .spec_runtime_renderer import render_enterprise_runtime_bundle
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
            "Generated files remain inside the governed workspace runtime",
        ],
        decisions=[
            "Use the validated ApplicationSpec as the only domain source of truth",
            "Fail closed when a deterministic business-rule expression is unsupported",
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
                    "Role policies and supported backend business rules derive from ApplicationSpec"
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
                title=f"Generate deterministic rule tests for {name}",
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
    bundle = render_enterprise_runtime_bundle(
        scenario.requirements,
        scenario.application_spec,
    )
    model = EnterpriseProjectModel.from_spec(
        scenario.requirements,
        scenario.application_spec,
    )
    role = system.lower()
    files = [file for file in bundle.files if _owned_by_role(file, model, role)]
    if "qa specialist" in role:
        files.append(
            GeneratedFile(
                path=model.test_path("Usings.cs"),
                content="global using Xunit;\n",
            )
        )
    return ArtifactSet(files=files)


def _owned_by_role(file: GeneratedFile, model: EnterpriseProjectModel, role: str) -> bool:
    path = file.path
    if "database specialist" in role:
        return path.startswith(model.api_path("Infrastructure/"))
    if "backend specialist" in role:
        return path.startswith(f"backend/{model.api_project}/") and (
            "/Infrastructure/" not in path and not path.endswith("/Dockerfile")
        )
    if "frontend specialist" in role:
        return path.startswith("frontend/") and path != "frontend/Dockerfile"
    if "qa specialist" in role:
        return path.startswith(f"backend/{model.test_project}/") or path.startswith("tests/")
    if "devops specialist" in role:
        return (
            path.endswith("/Dockerfile")
            or path in {"frontend/Dockerfile", "docker-compose.yml", "README.generated.md"}
            or path == "application-spec.json"
        )
    raise ValueError("Spec-driven fixture could not identify specialist role")
