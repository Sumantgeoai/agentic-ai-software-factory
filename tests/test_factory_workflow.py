from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from software_factory.config import Settings
from software_factory.contracts import CodeBundle, GeneratedFile, ProjectRequest
from software_factory.model_gateway import FixtureModelGateway
from software_factory.service import SoftwareFactoryService

T = TypeVar("T", bound=BaseModel)


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
    assert result.quality.passed
    assert result.repair_attempts == 0
    assert (Path(result.execution.workspace) / "app" / "main.py").exists()
    assert {item.owner.value for item in result.plan.items} >= {"backend", "qa"}


class RepairingFixtureGateway(FixtureModelGateway):
    def __init__(self) -> None:
        self.bundle_calls = 0

    async def complete(self, schema: type[T], *, system: str, user: str) -> T:
        if schema is CodeBundle:
            self.bundle_calls += 1
            if self.bundle_calls == 1:
                broken = CodeBundle(
                    files=[GeneratedFile(path="app/main.py", content="def broken(:\n")],
                    validation_commands=["compile"],
                )
                return schema.model_validate(broken.model_dump())
        return await super().complete(schema, system=system, user=user)


@pytest.mark.asyncio
async def test_failed_build_is_repaired_without_human_intervention(tmp_path: Path) -> None:
    gateway = RepairingFixtureGateway()
    service = SoftwareFactoryService(
        Settings(
            model_provider="fixture",
            workspace_root=tmp_path,
            command_timeout_seconds=30,
            max_repair_attempts=2,
        ),
        model=gateway,
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
    assert result.repair_attempts == 1
    assert gateway.bundle_calls == 2
