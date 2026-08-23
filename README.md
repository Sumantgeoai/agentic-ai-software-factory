# Agentic AI Software Factory

A governed multi-agent runtime that turns a product request into an implementation plan and a verified software workspace. Reasoning is separated from side effects: agents produce typed decisions; deterministic tools own filesystem and command execution.

## What is implemented

- Product Owner, Solution Architect, Planner, Backend, QA and Reviewer responsibilities
- LangGraph workflow with typed project state
- NVIDIA NIM/OpenAI-compatible model gateway, defaulting to Nemotron 3.5 Lightning
- deterministic fixture gateway for local development and CI
- bounded autonomous repair loop driven by build/test evidence
- sandboxed workspace writes with path validation and idempotent tool calls
- named command allow-list instead of arbitrary shell access
- MCP v2 server boundary for governed workspace tools
- FastAPI control API
- React/TypeScript control center
- essential unit and end-to-end workflow tests

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn apps.api.main:app --host 0.0.0.0 --port 8080 --reload
```

The default `fixture` provider makes the repository runnable without an API key. To use NVIDIA NIM:

```bash
set SOFTWARE_FACTORY_MODEL_PROVIDER=nvidia
set SOFTWARE_FACTORY_NVIDIA_API_KEY=<key>
```

On Linux/macOS use `export` instead of `set`.

Run the control center separately:

```bash
cd apps/control-center
npm install
npm run dev
```

## API

`POST /api/v1/projects/run`

```json
{
  "request": "Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports."
}
```

A successful run writes a generated application into `workspaces/<project-id>/`, runs compile and test gates, and returns the requirements, architecture, task plan, execution evidence and release decision.

## MCP

The MCP server exposes only governed operations. It never exposes a raw shell or host filesystem.

```bash
python -m software_factory.mcp_server
```

Use the MCP Inspector or another MCP host to connect to the server.

## Architecture

See `docs/DEVELOPMENT_PLAN.md` and `docs/adr/0001-governed-agent-runtime.md`.
