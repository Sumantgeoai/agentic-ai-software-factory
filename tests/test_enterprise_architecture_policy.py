import pytest

from software_factory.agents import SolutionArchitectAgent
from software_factory.contracts import ProjectRequest, TargetProfile
from software_factory.scenario_fixtures import SCENARIOS
from software_factory.spec_fixture_gateway import SpecDrivenFixtureModelGateway


@pytest.mark.asyncio
async def test_enterprise_architecture_matches_selected_current_stack() -> None:
    request = ProjectRequest(
        request=(
            "Build an employee leave-management application where employees submit leave, "
            "managers approve or reject requests, and HR can view reports."
        ),
        target_profile=TargetProfile.ENTERPRISE_DOTNET_REACT,
    )
    architecture = await SolutionArchitectAgent(SpecDrivenFixtureModelGateway()).run(
        request,
        SCENARIOS[0].requirements,
    )

    assert architecture.backend == "ASP.NET Core Web API / .NET 10"
    assert architecture.frontend == "React 19 + TypeScript 7 + React Router 7 + Vite 8"
    assert "PostgreSQL 16" in architecture.database
    assert "OIDC/JWT" in architecture.authentication
