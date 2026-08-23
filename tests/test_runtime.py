from pathlib import Path

import pytest

from software_factory.contracts import ToolRequest
from software_factory.runtime import WorkspacePolicy, WorkspaceRuntime


@pytest.mark.asyncio
async def test_tool_registry_is_idempotent(tmp_path: Path) -> None:
    runtime = WorkspaceRuntime(WorkspacePolicy(tmp_path))
    request = ToolRequest(
        name="workspace.write_text",
        arguments={"project_id": "p1", "path": "a.txt", "content": "first"},
        idempotency_key="same-call",
    )
    first = await runtime.registry.execute(request)
    second = await runtime.registry.execute(
        request.model_copy(update={"arguments": {**request.arguments, "content": "second"}})
    )
    assert first.success and second.success
    assert (tmp_path / "p1" / "a.txt").read_text() == "first"


@pytest.mark.asyncio
async def test_runtime_rejects_unlisted_command(tmp_path: Path) -> None:
    runtime = WorkspaceRuntime(WorkspacePolicy(tmp_path))
    result = await runtime.registry.execute(
        ToolRequest(
            name="workspace.run_validation",
            arguments={"project_id": "p1", "command": "shell"},
            idempotency_key="reject-shell",
        )
    )
    assert not result.success
    assert "allow-listed" in (result.error or "")
