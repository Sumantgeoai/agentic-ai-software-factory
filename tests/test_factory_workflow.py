from pathlib import Path

import pytest

from software_factory.config import Settings
from software_factory.contracts import ProjectRequest
from software_factory.service import SoftwareFactoryService


@pytest.mark.asyncio
async def test_leave_management_release_candidate_passes(tmp_path: Path) -> None:
    service = SoftwareFactoryService(
        Settings(model_provider="fixture", workspace_root=tmp_path, command_timeout_seconds=30)
    )
    result = await service.run(
        ProjectRequest(
            request=(
                "Build an employee leave-management application where employees submit leave, "
                "managers approve or reject requests, and HR can view reports."
            )
        )
    )

    assert result.review.approved
    assert result.execution.passed
    assert (Path(result.execution.workspace) / "app" / "main.py").exists()
    assert {item.owner.value for item in result.plan.items} >= {"backend", "qa"}
