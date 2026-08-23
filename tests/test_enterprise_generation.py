from pathlib import Path
from zipfile import ZipFile

import pytest

from software_factory.config import Settings
from software_factory.contracts import ProjectRequest
from software_factory.service import SoftwareFactoryService


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        model_provider="fixture",
        workspace_root=tmp_path / "workspaces",
        database_url=f"sqlite:///{tmp_path / 'factory.db'}",
        command_timeout_seconds=30,
    )


@pytest.mark.asyncio
async def test_enterprise_dotnet_react_profile_generates_role_aware_release(tmp_path: Path) -> None:
    service = SoftwareFactoryService(_settings(tmp_path))
    result = await service.run(
        ProjectRequest(
            request=(
                "Build an employee leave-management application where employees submit leave, "
                "managers approve or reject requests, and HR can view reports."
            ),
            target_profile="enterprise-dotnet-react",
        )
    )

    assert result.review.approved
    assert result.quality.passed
    assert result.security.passed
    assert result.release is not None

    files = set(result.execution.files_written)
    assert {
        "backend/LeaveManagement.Api/LeaveManagement.Api.csproj",
        "backend/LeaveManagement.Api/Program.cs",
        "backend/LeaveManagement.Api/Domain/LeaveRequest.cs",
        "backend/LeaveManagement.Api/Infrastructure/AppDbContext.cs",
        "backend/LeaveManagement.Api/Infrastructure/Migrations/202608240001_Initial.cs",
        "backend/LeaveManagement.Tests/LeaveRequestTests.cs",
        "frontend/package.json",
        "frontend/src/App.tsx",
        "frontend/src/pages.tsx",
        "docker-compose.yml",
    } <= files

    workspace = Path(result.execution.workspace)
    program = (workspace / "backend/LeaveManagement.Api/Program.cs").read_text(encoding="utf-8")
    domain = (workspace / "backend/LeaveManagement.Api/Domain/LeaveRequest.cs").read_text(
        encoding="utf-8"
    )
    frontend = (workspace / "frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'RequireAuthorization("EmployeeOnly")' in program
    assert 'RequireAuthorization("ManagerOnly")' in program
    assert 'RequireAuthorization("HrOnly")' in program
    assert "LEAVE_NOT_PENDING" in domain
    assert "LEAVE_SELF_APPROVAL_FORBIDDEN" in domain
    assert 'path="/leaves"' in frontend
    assert 'path="/approvals"' in frontend
    assert 'path="/reports"' in frontend

    events = service.run_store.list_events(result.project_id)
    specification = next(event for event in events if event.event_type == "specification.completed")
    assert specification.payload["target_profile"] == "enterprise-dotnet-react"
    assert specification.payload["roles"] == 3
    assert specification.payload["pages"] == 5
    assert specification.payload["business_rules"] == 5

    with ZipFile(result.release.path) as archive:
        names = set(archive.namelist())
        assert "backend/LeaveManagement.Api/Program.cs" in names
        assert "frontend/src/App.tsx" in names
        assert "docker-compose.yml" in names
        assert "release-manifest.json" in names
