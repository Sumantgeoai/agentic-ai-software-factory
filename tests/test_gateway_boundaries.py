import pytest

from software_factory.contracts import RequirementSpec
from software_factory.model_gateway import FixtureModelGateway
from software_factory.scenario_fixtures import SCENARIOS
from software_factory.spec_fixture_gateway import SpecDrivenFixtureModelGateway


@pytest.mark.asyncio
async def test_lightweight_fixture_fails_closed_for_enterprise_profile() -> None:
    gateway = FixtureModelGateway()

    with pytest.raises(ValueError, match="SpecDrivenFixtureModelGateway"):
        await gateway.complete(
            RequirementSpec,
            system="product owner",
            user="Target profile: enterprise-dotnet-react\nRequest: Build a complaint portal",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item.key)
async def test_spec_driven_fixture_resolves_each_enterprise_domain(scenario) -> None:
    gateway = SpecDrivenFixtureModelGateway()
    request_by_key = {
        "leave": "Build an employee leave management workflow",
        "complaint": "Build a citizen complaint portal and officer workflow",
        "asset": "Build an asset inspection management application",
    }

    requirements = await gateway.complete(
        RequirementSpec,
        system="product owner",
        user=(
            "Target profile: enterprise-dotnet-react\n"
            f"Request: {request_by_key[scenario.key]}"
        ),
    )

    assert requirements.product_name == scenario.requirements.product_name
