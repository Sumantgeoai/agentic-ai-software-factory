# Development Plan

## Goal
Build an autonomous, governed software delivery system that can take a product requirement, decompose it into role-specific work, execute engineering tasks through controlled tools, verify results, and produce a runnable release candidate.

The system must separate probabilistic reasoning from deterministic execution. Agents plan and decide; controlled runtimes perform file, build, test, database, and deployment operations.

## Engineering Principles

- Keep agents role-focused with explicit inputs, outputs, permissions, and acceptance criteria.
- Prefer structured contracts over free-form agent-to-agent chat.
- Keep all side effects behind a policy-enforced tool runtime.
- Make every execution traceable, retry-safe, and resumable.
- Use project state rather than forwarding full conversation history between agents.
- Treat generated code like normal production code: idiomatic structure, tests, reviews, ADRs, linting, and CI.
- Avoid generic scaffolding, excessive comments, artificial prose, and fake commit history.
- Keep model providers replaceable behind a model gateway.

## Target Architecture

User / Control Center
→ FastAPI API
→ LangGraph Supervisor
→ Product Owner / Architect / Planner
→ Task DAG + Scheduler
→ Specialist Agents
→ Policy Engine
→ Tool Registry / MCP
→ Isolated Workspace Runtime
→ Build / Test / Security Gates
→ Release Candidate

Shared state:
- PostgreSQL for projects, requirements, decisions, tasks, runs, checkpoints, defects, and audit records.
- Redis for short-lived coordination, locks, and queue state.
- Artifact storage for generated source, reports, test outputs, and release bundles.
- pgvector only when retrieval is actually required.

## Initial Agent Roles

### Product Owner Agent
Turns an unstructured product request into scope, actors, functional requirements, non-functional requirements, constraints, and acceptance criteria.

### Solution Architect Agent
Produces an implementation architecture, technology decisions, service boundaries, data ownership, security constraints, and ADRs.

### Planner Agent
Converts approved requirements and architecture into a dependency-aware task DAG with ownership and acceptance criteria.

### Backend Agent
Implements API/domain/backend tasks through governed tools and must verify build/tests before declaring completion.

### Frontend Agent
Implements UI tasks and verifies type-check, build, and relevant UI tests.

### Database Agent
Creates schema/migrations and validates changes in an isolated database environment.

### QA Agent
Runs deterministic test suites, creates defects with reproducible evidence, and routes failed work back through the planner.

### Reviewer Agent
Validates task acceptance criteria, architecture compliance, test evidence, and unresolved risks before release.

## Delivery Phases

### Phase 0 — Engineering Baseline
- Repository structure
- Python project/tooling baseline
- FastAPI service skeleton
- Configuration model
- Logging and correlation IDs
- Test/lint/type-check baseline
- Docker development baseline
- ADR structure

Exit criteria: clean local start, health endpoint, automated tests and static checks passing.

### Phase 1 — Durable Planning Workflow
- Project and requirement models
- Product Owner Agent
- Solution Architect Agent
- Planner Agent
- LangGraph orchestration
- Structured outputs with Pydantic
- Model gateway abstraction
- In-memory state first, PostgreSQL persistence within the phase

Exit criteria: one product request reliably becomes validated requirements, architecture, and a task DAG.

### Phase 2 — Governed Tool Runtime
- Tool registry
- Policy checks
- Workspace boundary
- Filesystem operations
- Command allow-listing
- Execution timeout/resource limits
- Retry and idempotency contracts
- Audit events
- MCP adapter boundary

Exit criteria: an agent can safely modify a sandbox project and execute an approved deterministic command without unrestricted host access.

### Phase 3 — Autonomous Backend Vertical Slice
- Backend Agent
- Build/test feedback loop
- Defect model
- QA Agent
- Planner reassignment
- Checkpoint/resume

Exit criteria: requirement → backend code → failing test/build feedback → autonomous correction → passing result.

### Phase 4 — Full-Stack Application Factory
- Frontend Agent
- Database Agent
- integration workflow
- isolated application runtime
- Playwright/API integration tests
- Reviewer Agent
- release bundle

Exit criteria: a small full-stack requirement produces a runnable release candidate with source, migrations, tests, architecture, and execution evidence.

### Phase 5 — Production Hardening
- Authentication/RBAC
- per-agent and per-tool authorization
- secret broker
- network egress policy
- persistent job queue
- concurrency controls
- quotas/token/cost budgets
- OpenTelemetry tracing
- evaluation dataset and CI quality gates
- SAST/dependency/secret scans
- approval gates for high-risk operations

### Phase 6 — Multi-Agent Platform Extensions
- dynamic agent provisioning by project type
- agent capability registry
- A2A-compatible communication where useful
- richer MCP ecosystem
- multiple model routing/fallback
- reusable project templates
- Kubernetes worker isolation when scale requires it

## Model Strategy

Initial development uses a provider-neutral model gateway.

Preferred pattern:
- Nemotron 3.5 Lightning for high-volume tool-oriented agent work when available.
- Optional stronger reasoning model for complex architecture/planning tasks.
- deterministic validation on every model response.

No component may depend directly on one model provider SDK outside the gateway layer.

## Repository Direction

Expected top-level structure:

```text
apps/
  api/
  control-center/
packages/
  agents/
  orchestration/
  contracts/
  model_gateway/
  runtime/
  tools/
  policies/
  persistence/
  observability/
tests/
docs/
  adr/
infra/
```

The exact structure may evolve through ADRs; we will not create empty abstractions before they have a concrete responsibility.

## First Demonstration Scenario

Input:
"Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports."

Expected automated flow:
1. Product Owner Agent creates validated requirements and acceptance criteria.
2. Architect Agent defines React + ASP.NET Core + PostgreSQL style target architecture, or another stack selected by project policy.
3. Planner creates a dependency-aware implementation DAG.
4. Specialist agents implement database, backend, frontend, and integration work.
5. QA executes tests and returns reproducible defects to the planner.
6. Agents repair failed work within bounded retry policies.
7. Reviewer evaluates quality gates.
8. System emits a runnable release candidate and audit trail.

## What We Will Not Do

- Give the LLM unrestricted shell, filesystem, Docker socket, database admin, or credential access.
- Depend on agent role-play conversations as the execution mechanism.
- Mark work complete based only on an LLM statement.
- Auto-deploy destructive or privileged production changes without policy/approval gates.
- Hide AI assistance or fabricate human-authored provenance. The repository should look like a serious engineering project because of its architecture, tests, decisions, and incremental implementation—not through deceptive history.
