# Agentic AI Software Factory

A governed multi-agent software-generation runtime that converts a product request into typed requirements, architecture, specialist artifacts, deterministic validation evidence and a reproducible release package. Probabilistic reasoning is separated from side effects: agents plan and generate structured artifacts; the runtime owns filesystem access, validation commands, security gates, audit persistence and release promotion.

## What is implemented

- Product Owner, Solution Architect and dependency-aware Planner agents
- specialist Database, Backend, Frontend, QA and DevOps artifact agents
- LangGraph orchestration with a sequential fallback for dependency-light execution
- NVIDIA NIM/OpenAI-compatible model gateway plus deterministic fixture gateway for CI/demo
- deterministic pre-execution SecurityAgent scanning generated artifacts
- governed workspace writes with path validation and generation-aware idempotency keys
- named validation command allow-list instead of arbitrary shell access
- bounded autonomous repair loop with mandatory security re-scan before re-execution
- evidence-based Reviewer that requires both quality and security gates to pass
- deterministic release ZIP with SHA-256 digest and per-file release manifest
- SQL-backed run lifecycle and ordered audit events; SQLite locally and PostgreSQL-compatible configuration
- API-key protection for v1 routes when configured
- validated `X-Correlation-ID` propagation through HTTP, OpenTelemetry spans and audit events
- authenticated run-status and audit-trace retrieval endpoints
- MCP v2 boundary for governed workspace tools; no raw shell or host filesystem tool
- React/TypeScript control center for run, security, validation, audit and release evidence
- Docker baseline with non-root execution, read-only root filesystem and persistent data/workspace volumes
- focused backend/workflow/API tests and frontend production-build CI

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn apps.api.main:app --host 127.0.0.1 --port 8080 --reload
```

The default `fixture` provider makes the repository runnable without model credentials. To use NVIDIA NIM:

```bash
set SOFTWARE_FACTORY_MODEL_PROVIDER=nvidia
set SOFTWARE_FACTORY_NVIDIA_API_KEY=<key>
```

On Linux/macOS use `export` instead of `set`.

For pilot/staging API protection:

```bash
set SOFTWARE_FACTORY_API_KEY=<random-secret>
```

The control center accepts that key in memory for the current tab. Do **not** put API keys in `VITE_*` variables because those values are shipped to the browser bundle.

Run the control center separately:

```bash
cd apps/control-center
cp .env.example .env
npm install
npm run dev
```

## Container demo

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

The compose deployment binds the API to `127.0.0.1:8080` by default. Put a TLS/authenticated gateway in front of it when exposing it beyond the local host.

## API

Start a run:

```text
POST /api/v1/projects/run
X-API-Key: <configured key, when enabled>
X-Correlation-ID: <caller correlation id, optional>
```

```json
{
  "request": "Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports."
}
```

Inspect persisted state and audit evidence:

```text
GET /api/v1/runs/{project_id}
GET /api/v1/runs/{project_id}/audit
```

A successful run writes only governed generated files into the project workspace, executes the allow-listed compile/test gates, evaluates deterministic security evidence, persists the lifecycle trace and creates a release ZIP with an embedded file manifest.

## MCP

The MCP server exposes only governed operations. It never exposes a raw shell or unrestricted host filesystem.

```bash
python -m software_factory.mcp_server
```

Use an MCP Inspector or another MCP host to connect to the server.

## Architecture and production boundary

The current container is appropriate for portfolio/pilot and controlled staging use. It is **not** presented as a final multi-tenant production execution plane because generated validation still runs inside the API container. Production should move execution to isolated per-run workers behind a durable queue while keeping the same typed planning, security, idempotency and audit contracts.

See:

- `docs/DEVELOPMENT_PLAN.md`
- `docs/DEPLOYMENT.md`
- `docs/adr/0001-governed-agent-runtime.md`
