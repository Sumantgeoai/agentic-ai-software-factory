# Portfolio v1 Acceptance

This document defines the completion boundary for the portfolio-grade vertical slice described by the development plan. It does not re-label the repository as a finished multi-tenant production platform. Production hardening and platform extensions remain an explicit backlog in Phases 5 and 6.

## Accepted v1 scope

The portfolio v1 is accepted when all of the following are true on `main` and CI is green:

| Area | Acceptance evidence |
| --- | --- |
| Product intake | A typed `ProjectRequest` becomes validated requirements and measurable acceptance criteria. |
| Architecture | The Architect emits a structured architecture with service, security and technology decisions. |
| Planning | The Planner emits a dependency-aware DAG with explicit specialist ownership. |
| Specialist generation | Database, Backend, Frontend, QA and DevOps agents emit role-scoped artifacts rather than sharing unrestricted execution access. |
| Deterministic execution | Generated files are materialized only through the governed workspace runtime; validation commands are selected from the named allow-list. |
| Security boundary | Deterministic security scanning runs before any workspace side effect and again after a repair. A blocking finding produces no workspace execution and no release. |
| Repair | Failed deterministic validation can trigger a bounded repair, followed by another security scan and validation attempt. |
| Review | Reviewer approval requires both deterministic quality and security evidence. |
| Persistence | Run lifecycle and ordered audit events are stored through the SQL-backed run store; terminal state and terminal lifecycle event are committed atomically. |
| Correlation / tracing | Validated correlation IDs flow through HTTP responses, OpenTelemetry spans and audit event payloads. |
| API boundary | v1 routes can require a configured API key; run and audit retrieval are authenticated under the same boundary; public responses do not reveal internal workspace or release filesystem paths. |
| Release | An approved run creates a deterministic ZIP containing only governed generated files plus a SHA-256 manifest; the demonstration release contains runtime dependencies and startup instructions. |
| Control center | The React UI can submit an authenticated correlated run and show persisted status, plan, validation, security, release digest and audit evidence. |
| Delivery baseline | Backend Ruff/pytest and control-center production build are CI gates. Container defaults use a non-root process, read-only root filesystem, dropped capabilities and persistent data/workspace volumes. |

## First demonstration acceptance

Input:

```text
Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports.
```

The deterministic fixture scenario intentionally chooses a dependency-light FastAPI/Python implementation with a browser UI and in-memory demo repository. The plan permits a policy-selected stack, so the demonstration is not required to imitate React + ASP.NET Core + PostgreSQL merely for appearance.

Expected evidence from one successful run:

1. Product Owner requirements and acceptance criteria are present.
2. Architecture and dependency-aware plan are present.
3. Database, Backend, Frontend, QA and DevOps specialists contribute governed files.
4. Security gate passes before materialization.
5. Compile and test commands pass through the runtime allow-list.
6. Reviewer approves only after security and quality pass.
7. Release ZIP contains application source, tests, browser UI, `requirements.txt`, startup instructions and `release-manifest.json`.
8. Persisted audit includes at least `run.started`, requirements, architecture, plan, security, validation, quality, review, release and `run.completed` events.
9. API response exposes the project/correlation/evidence required by the control center without disclosing host workspace or release paths.

A dedicated repair test additionally proves that a broken generated backend is repaired within the retry budget. A dedicated security test proves that a generated hard-coded secret is stopped before any workspace is created.

## Production boundary

The current vertical slice is suitable for portfolio demonstration, local use and controlled staging. It is not a final untrusted multi-tenant production executor because generated validation still runs in the API container/process boundary.

The following development-plan items are intentionally **not** part of portfolio v1 completion and remain production/platform backlog:

- enterprise OIDC/RBAC and tenant/project entitlements;
- per-agent/per-tool authorization beyond the current deterministic runtime policy;
- secret broker and outbound network egress policy;
- durable job queue, worker leases, distributed concurrency controls and quotas/cost budgets;
- isolated disposable execution workers or Kubernetes sandboxing for untrusted generated code;
- Redis coordination and distributed locks;
- managed PostgreSQL HA/backups plus immutable external artifact/object storage;
- checkpoint/resume across process or worker failure and richer defect/planner reassignment models;
- dependency/SAST scanners beyond the current deterministic secret/dangerous-code gate;
- Playwright/browser integration coverage and a broader evaluation dataset;
- multi-model routing/fallback, dynamic agents and wider MCP/A2A ecosystem.

Those are production evolution items, not hidden gaps. `docs/DEPLOYMENT.md` defines the target topology and promotion requirements so the repository does not imply that a portfolio container is equivalent to an enterprise production execution plane.

## Final verification rule

Portfolio v1 is complete only after the final acceptance pull request has both repository CI jobs green: backend (`ruff`, `pytest`) and control center (`npm run build`). If either fails, completion is blocked until the exact failure is fixed and the full required jobs pass again.
