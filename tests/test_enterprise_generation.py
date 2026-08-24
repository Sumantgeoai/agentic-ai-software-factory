from pathlib import Path
from zipfile import ZipFile

import pytest

from software_factory.config import Settings
from software_factory.contracts import ProjectRequest
from software_factory.project_model import EnterpriseProjectModel
from software_factory.scenario_fixtures import SCENARIOS
from software_factory.service import SoftwareFactoryService


REQUESTS = {
    "leave": (
        "Build an employee leave-management application where employees submit leave, "
        "managers approve or reject requests, and HR can view reports."
    ),
    "complaint": (
        "Build a citizen complaint portal where citizens submit complaints, officers work "
        "assigned complaints, and supervisors monitor operations."
    ),
    "asset": (
        "Build an asset inspection manager where inspectors record inspections, supervisors "
        "review team inspections, and asset managers view portfolio condition."
    ),
}


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        model_provider="fixture",
        workspace_root=tmp_path / "workspaces",
        database_url=f"sqlite:///{tmp_path / 'factory.db'}",
        command_timeout_seconds=30,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item.key)
async def test_enterprise_profile_generates_spec_driven_release(tmp_path: Path, scenario) -> None:
    service = SoftwareFactoryService(_settings(tmp_path))
    result = await service.run(
        ProjectRequest(
            request=REQUESTS[scenario.key],
            target_profile="enterprise-dotnet-react",
        )
    )

    assert result.review.approved
    assert result.quality.passed
    assert result.security.passed
    assert result.release is not None
    assert result.requirements.product_name == scenario.requirements.product_name

    model = EnterpriseProjectModel.from_spec(scenario.requirements, scenario.application_spec)
    files = set(result.execution.files_written)
    assert {
        model.api_path(f"{model.api_project}.csproj"),
        model.api_path("Program.cs"),
        model.api_path("Domain/BusinessRules.cs"),
        model.api_path("Infrastructure/AppDbContext.cs"),
        model.api_path("Infrastructure/Migrations/202608240001_Initial.cs"),
        model.test_path(f"{model.test_project}.csproj"),
        model.test_path("BusinessRuleTests.cs"),
        "frontend/package.json",
        "frontend/src/App.tsx",
        "frontend/src/main.tsx",
        "docker-compose.yml",
        "application-spec.json",
    } <= files

    workspace = Path(result.execution.workspace)
    program = (workspace / model.api_path("Program.cs")).read_text(encoding="utf-8")
    rules = (workspace / model.api_path("Domain/BusinessRules.cs")).read_text(
        encoding="utf-8"
    )
    frontend = (workspace / "frontend/src/App.tsx").read_text(encoding="utf-8")

    assert "RequireAuthorization" in program
    assert "UseNpgsql" in program
    for rule in scenario.application_spec.business_rules:
        assert rule.error_code in rules
    for page in scenario.application_spec.pages:
        assert f'path="{page.route}"' in frontend

    events = service.run_store.list_events(result.project_id)
    specification = next(event for event in events if event.event_type == "specification.completed")
    assert specification.payload["target_profile"] == "enterprise-dotnet-react"
    assert specification.payload["roles"] == len(scenario.application_spec.roles)
    assert specification.payload["pages"] == len(scenario.application_spec.pages)
    assert specification.payload["business_rules"] == len(
        scenario.application_spec.business_rules
    )

    with ZipFile(result.release.path) as archive:
        names = set(archive.namelist())
        assert model.api_path("Program.cs") in names
        assert "frontend/src/App.tsx" in names
        assert "docker-compose.yml" in names
        assert "release-manifest.json" in names
