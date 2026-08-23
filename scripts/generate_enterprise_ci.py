from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from software_factory.config import Settings
from software_factory.contracts import ProjectRequest
from software_factory.service import SoftwareFactoryService

ROOT = Path(".generated-enterprise")
WORKSPACE_ROOT = ROOT / "workspaces"
OUTPUT = ROOT / "release-workspace"


async def _generate() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)

    settings = Settings(
        model_provider="fixture",
        workspace_root=WORKSPACE_ROOT,
        database_url=f"sqlite:///{ROOT / 'factory.db'}",
        command_timeout_seconds=60,
    )
    service = SoftwareFactoryService(settings)
    result = await service.run(
        ProjectRequest(
            request=(
                "Build an employee leave-management application where employees submit leave, "
                "managers approve or reject requests, and HR can view reports."
            ),
            target_profile="enterprise-dotnet-react",
        ),
        correlation_id="enterprise-native-ci",
    )
    if not result.review.approved or not result.release:
        raise RuntimeError("Enterprise fixture did not pass governed factory review")

    source = Path(result.execution.workspace)
    shutil.copytree(source, OUTPUT)
    print(OUTPUT.as_posix())


if __name__ == "__main__":
    asyncio.run(_generate())
