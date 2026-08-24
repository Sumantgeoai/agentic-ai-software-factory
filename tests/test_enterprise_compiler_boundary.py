import pytest

from software_factory.agents import BackendAgent
from software_factory.contracts import (
    AgentRole,
    ArchitectureSpec,
    ArtifactSet,
    TaskPlan,
    WorkItem,
)
from software_factory.scenario_fixtures import SCENARIOS


class RejectArtifactModel:
    async def complete(self, schema, *, system: str, user: str):  # type: ignore[no-untyped-def]
        if schema is ArtifactSet:
            raise AssertionError("Enterprise specialist source must not be emitted by the LLM")
        raise AssertionError(f"Unexpected model call for {schema.__name__}")


def _architecture() -> ArchitectureSpec:
    return ArchitectureSpec(
        summary="Enterprise compiled application",
        backend="ASP.NET Core Web API / .NET 10",
        frontend="React 19 + TypeScript 7",
        database="PostgreSQL 16",
        authentication="OIDC/JWT",
        services=["api", "web", "postgres"],
        security_constraints=["Backend authorization is authoritative"],
        decisions=["Compile source from validated ApplicationSpec"],
    )


@pytest.mark.asyncio
async def test_enterprise_backend_source_is_compiled_without_llm_artifact_call() -> None:
    scenario = SCENARIOS[1]
    plan = TaskPlan(
        items=[
            WorkItem(
                id="API-1",
                title="Compile backend",
                owner=AgentRole.BACKEND,
                acceptance_criteria=["Backend source derives from ApplicationSpec"],
            )
        ]
    )
    agent = BackendAgent(RejectArtifactModel())  # type: ignore[arg-type]

    artifacts = await agent.run(
        scenario.requirements,
        _architecture(),
        scenario.application_spec,
        plan,
    )

    paths = {file.path for file in artifacts.files}
    assert any(path.endswith("/Program.cs") for path in paths)
    assert any(path.endswith("/Authorization/ResourceScopes.cs") for path in paths)
    assert any(path.endswith("/Domain/BusinessRules.cs") for path in paths)
