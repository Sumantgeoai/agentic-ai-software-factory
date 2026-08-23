from __future__ import annotations

from .config import Settings
from .contracts import ToolRequest
from .runtime import WorkspacePolicy, WorkspaceRuntime


def create_server():  # type: ignore[no-untyped-def]
    from mcp.server import MCPServer

    settings = Settings.from_env()
    runtime = WorkspaceRuntime(
        WorkspacePolicy(settings.workspace_root, timeout_seconds=settings.command_timeout_seconds)
    )
    server = MCPServer(
        "software-factory-tools",
        instructions=(
            "Governed software workspace tools. Paths are sandboxed and validation commands are "
            "selected by name; raw shell execution is not available."
        ),
    )

    @server.tool()
    async def write_text(project_id: str, path: str, content: str) -> dict[str, object]:
        result = await runtime.registry.execute(
            ToolRequest(
                name="workspace.write_text",
                arguments={"project_id": project_id, "path": path, "content": content},
                idempotency_key=f"mcp:{project_id}:write:{path}:{hash(content)}",
            )
        )
        if not result.success:
            raise ValueError(result.error or "Write failed")
        return result.output

    @server.tool()
    async def run_validation(project_id: str, command: str) -> dict[str, object]:
        result = await runtime.registry.execute(
            ToolRequest(
                name="workspace.run_validation",
                arguments={"project_id": project_id, "command": command},
                idempotency_key=f"mcp:{project_id}:validation:{command}",
            )
        )
        if not result.success:
            raise ValueError(result.error or "Validation failed")
        return result.output

    return server


if __name__ == "__main__":
    create_server().run(transport="stdio")
