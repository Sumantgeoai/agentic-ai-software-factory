from pathlib import Path
from typing import TypeVar
from zipfile import ZipFile

import pytest
from pydantic import BaseModel

from software_factory.config import Settings
from software_factory.contracts import ArtifactSet, CodeBundle, GeneratedFile, ProjectRequest
from software_factory.model_gateway import FixtureModelGateway
from software_factory.service import SoftwareFactoryService

T = TypeVar("T", bound=BaseModel)


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "model_provider": "fixture",
        "workspace_root": tmp_path / "workspaces",
        "database_url": f"sqlite:///{tmp_path / 'factory.db'}",
        "command_timeout_seconds": 30,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _request() -> ProjectRequest:
    return ProjectRequest(
        request=(
            "Build an employee leave-management application where employees submit leave, "
            "managers approve or reject requests, and HR can view reports."
        )
    )


@pytest.mark.asyncio
async def test_leave_management_release_candidate_passes(tmp_path: Path) -> None:
    service = SoftwareFactoryService(_settings(tmp_path))
    result = await service.run(_request())

    assert result.review.approved
    assert result.quality.passed
    assert result.security.passed
    assert result.repair_attempts == 0
    assert result.release is not None
    assert Path(result.release.path).exists()
    assert (Path(result.execution.workspace) / "app" / "main.py").exists()
    assert {item.owner.value for item in result.plan.items} >= {
        "database",
        "backend",
        "frontend",
        "qa",
        "devops",
    }

    with ZipFile(result.release.path) as archive:
        assert "release-manifest.json" in archive.namelist()
        assert "app/main.py" in archive.namelist()
        assert not any("__pycache__" in name for name in archive.namelist())

    stored = service.run_store.get_run(result.project_id)
    events = service.run_store.list_events(result.project_id)
    assert stored is not None and stored.status == "completed"
    assert stored.result is not None and stored.result.release == result.release
    assert {event.event_type for event in events} >= {
        "run.started",
        "requirements.completed",
        "architecture.completed",
        "plan.completed",
        "security.completed",
        "validation.executed",
        "quality.completed",
        "review.completed",
        "release.created",
        "run.completed",
    }


class RepairingFixtureGateway(FixtureModelGateway):
    def __init__(self) -> None:
        self.backend_artifact_calls = 0
        self.repair_calls = 0

    async def complete(self, schema: type[T], *, system: str, user: str) -> T:
        if schema is ArtifactSet and "backend specialist" in system.lower():
            self.backend_artifact_calls += 1
            broken = ArtifactSet(
                files=[GeneratedFile(path="app/main.py", content="def broken(:\n")]
            )
            return schema.model_validate(broken.model_dump())
        if schema is CodeBundle:
            self.repair_calls += 1
        return await super().complete(schema, system=system, user=user)


@pytest.mark.asyncio
async def test_failed_build_is_repaired_without_human_intervention(tmp_path: Path) -> None:
    gateway = RepairingFixtureGateway()
    service = SoftwareFactoryService(
        _settings(tmp_path, max_repair_attempts=2),
        model=gateway,
    )

    result = await service.run(_request())

    assert result.review.approved
    assert result.repair_attempts == 1
    assert result.security.passed
    assert result.release is not None
    assert gateway.backend_artifact_calls == 1
    assert gateway.repair_calls == 1


class SecretFixtureGateway(FixtureModelGateway):
    async def complete(self, schema: type[T], *, system: str, user: str) -> T:
        if schema is ArtifactSet and "backend specialist" in system.lower():
            unsafe = ArtifactSet(
                files=[
                    GeneratedFile(
                        path="app/main.py",
                        content="API_KEY = 'sk-abcdefghijklmnopqrstuvwx'\n",
                    )
                ]
            )
            return schema.model_validate(unsafe.model_dump())
        return await super().complete(schema, system=system, user=user)


@pytest.mark.asyncio
async def test_security_gate_blocks_workspace_execution_and_release(tmp_path: Path) -> None:
    service = SoftwareFactoryService(_settings(tmp_path), model=SecretFixtureGateway())

    result = await service.run(_request())

    assert not result.security.passed
    assert not result.review.approved
    assert not result.quality.passed
    assert result.execution.files_written == []
    assert result.execution.commands == []
    assert result.release is None
    assert not Path(result.execution.workspace).exists()
