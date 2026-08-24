from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path

from software_factory.config import Settings
from software_factory.contracts import ProjectRequest
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


async def _generate(scenario: str) -> None:
    root = Path(".generated-enterprise") / scenario
    workspace_root = root / "workspaces"
    output = root / "release-workspace"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    settings = Settings(
        model_provider="fixture",
        workspace_root=workspace_root,
        database_url=f"sqlite:///{root / 'factory.db'}",
        command_timeout_seconds=60,
    )
    service = SoftwareFactoryService(settings)
    result = await service.run(
        ProjectRequest(
            request=REQUESTS[scenario],
            target_profile="enterprise-dotnet-react",
        ),
        correlation_id=f"enterprise-native-ci-{scenario}",
    )
    if not result.review.approved or not result.release:
        raise RuntimeError(f"Enterprise scenario did not pass governed review: {scenario}")

    source = Path(result.execution.workspace)
    shutil.copytree(source, output)
    print(output.as_posix())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=sorted(REQUESTS))
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_generate(args.scenario))
