from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .contracts import CodeBundle, CommandEvidence, ExecutionEvidence, ToolRequest, ToolResult

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class WorkspacePolicy:
    def __init__(self, root: Path, timeout_seconds: float = 60.0) -> None:
        self.root = root.resolve()
        self.timeout_seconds = timeout_seconds
        self.allowed_commands = {
            "compile": [sys.executable, "-m", "compileall", "-q", "."],
            "test": [sys.executable, "-m", "pytest", "-q"],
        }

    def project_dir(self, project_id: str) -> Path:
        path = (self.root / project_id).resolve()
        if path == self.root or self.root not in path.parents:
            raise ValueError("Project workspace escaped configured root")
        return path

    def resolve_file(self, project_id: str, relative_path: str) -> Path:
        project_dir = self.project_dir(project_id)
        candidate = (project_dir / relative_path).resolve()
        if candidate == project_dir or project_dir not in candidate.parents:
            raise ValueError("File path escaped project workspace")
        return candidate


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._results: dict[str, ToolResult] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        if name in self._handlers:
            raise ValueError(f"Tool already registered: {name}")
        self._handlers[name] = handler

    async def execute(self, request: ToolRequest) -> ToolResult:
        cached = self._results.get(request.idempotency_key)
        if cached is not None:
            return cached
        handler = self._handlers.get(request.name)
        if handler is None:
            result = ToolResult(success=False, error=f"Unknown tool: {request.name}")
        else:
            try:
                result = ToolResult(success=True, output=await handler(request.arguments))
            except Exception as exc:
                result = ToolResult(success=False, error=str(exc))
        self._results[request.idempotency_key] = result
        return result


class WorkspaceRuntime:
    def __init__(self, policy: WorkspacePolicy) -> None:
        self.policy = policy
        self.registry = ToolRegistry()
        self.registry.register("workspace.write_text", self._write_text)
        self.registry.register("workspace.run_validation", self._run_validation)

    async def _write_text(self, args: dict[str, Any]) -> dict[str, Any]:
        project_id = str(args["project_id"])
        relative_path = str(args["path"])
        content = str(args["content"])
        if len(content.encode("utf-8")) > 250_000:
            raise ValueError("File exceeds workspace write limit")
        target = self.policy.resolve_file(project_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": relative_path, "bytes": len(content.encode("utf-8"))}

    async def _run_validation(self, args: dict[str, Any]) -> dict[str, Any]:
        project_id = str(args["project_id"])
        command_name = str(args["command"])
        command = self.policy.allowed_commands.get(command_name)
        if command is None:
            raise ValueError(f"Command is not allow-listed: {command_name}")
        workspace = self.policy.project_dir(project_id)
        workspace.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.policy.timeout_seconds
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise TimeoutError(f"Command timed out: {command_name}") from None
        return {
            "command": command_name,
            "return_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[-20_000:],
            "stderr": stderr.decode("utf-8", errors="replace")[-20_000:],
        }

    async def materialize(
        self, project_id: str, bundle: CodeBundle, *, generation: int = 0
    ) -> ExecutionEvidence:
        files_written: list[str] = []
        for index, file in enumerate(bundle.files):
            result = await self.registry.execute(
                ToolRequest(
                    name="workspace.write_text",
                    arguments={
                        "project_id": project_id,
                        "path": file.path,
                        "content": file.content,
                    },
                    idempotency_key=f"{project_id}:g{generation}:write:{index}:{file.path}",
                )
            )
            if not result.success:
                raise RuntimeError(result.error or "Workspace write failed")
            files_written.append(file.path)

        commands: list[CommandEvidence] = []
        for index, command_name in enumerate(bundle.validation_commands):
            result = await self.registry.execute(
                ToolRequest(
                    name="workspace.run_validation",
                    arguments={"project_id": project_id, "command": command_name},
                    idempotency_key=(
                        f"{project_id}:g{generation}:validate:{index}:{command_name}"
                    ),
                )
            )
            if not result.success:
                raise RuntimeError(result.error or f"Validation failed: {command_name}")
            evidence = CommandEvidence.model_validate(result.output)
            commands.append(evidence)
            if not evidence.passed:
                break

        return ExecutionEvidence(
            workspace=str(self.policy.project_dir(project_id)),
            files_written=files_written,
            commands=commands,
        )
