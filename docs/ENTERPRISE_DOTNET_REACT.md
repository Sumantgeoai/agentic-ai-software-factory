# Enterprise .NET + React Generation Profile

`enterprise-dotnet-react` is the production-oriented generation target for business applications that need explicit roles, multi-page navigation, backend-enforced business rules and durable relational persistence.

## Target stack

The governed baseline is intentionally explicit so the architecture evidence, generated source and native CI validate the same target:

- ASP.NET Core Web API on .NET 10;
- React 19 + TypeScript 7 + React Router 7 + Vite 8;
- PostgreSQL 16 with EF Core 10/Npgsql and explicit migrations;
- OIDC/JWT bearer authentication with backend role policies;
- Docker Compose for local integration;
- xUnit domain/authorization tests and React production-build validation.

The deterministic stack policy can move supported package patch versions without changing the application specification contract.

## Application specification boundary

Before specialist code generation, the factory must produce and validate a typed `ApplicationSpec` containing:

- roles and responsibilities;
- permissions with own/team/all scope;
- pages, routes and role visibility;
- domain entities and typed fields;
- workflows;
- explicit business rules with stable identifiers and error codes.

The application specification is the shared source of truth for Database, Backend, Frontend, QA and DevOps agents. Specialist agents must not independently invent conflicting roles, routes or business rules.

## Security rule

Frontend route guards, hidden navigation and form validation are user-experience controls only. They are never treated as an authorization boundary.

ASP.NET Core enforces identity, role policy, team/ownership scope and business rules server-side. PostgreSQL constraints are used where a rule can be safely expressed at the data layer, while domain/application rules remain explicit in backend code and tests. Generated validation commands remain behind the factory allow-list and source is scanned before workspace materialization.

The generated local Docker Compose file requires an external OIDC authority/audience for authenticated API use. The role selector in the generated React UI demonstrates navigation only; it does not manufacture a trusted identity or bypass API authorization.

## Reference scenario

The accepted enterprise scenario is Leave Management:

- Employee: create and view own leave requests.
- Manager: view only the managed-team approval queue and approve/reject only requests in that scope.
- HR: view organization-wide reporting.

Representative rules include:

- end date must not precede start date;
- only pending requests can be approved or rejected;
- an employee cannot approve their own request;
- leave requests must not overlap an existing approved request for the same employee;
- approved requests cannot be edited through the normal employee workflow;
- a manager cannot decide a request outside the authenticated team scope.

The exact rules are represented as structured `BusinessRuleSpec` records before code generation. The generated backend implements them and QA derives focused tests from the same specification.

## Demo from the control center

Run the factory API and control center using the repository README instructions. In the Control Center select **Enterprise · ASP.NET Core + React + PostgreSQL** and submit:

```text
Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports.
```

The UI sends the typed profile value `enterprise-dotnet-react`. A successful governed run should show:

1. architecture evidence identifying .NET 10, React 19/TypeScript 7 and PostgreSQL 16;
2. Database, Backend, Frontend, QA and DevOps work items;
3. deterministic security PASS before workspace execution;
4. generated backend authorization policies and manager team-scope enforcement;
5. generated React routes for employee, manager and HR pages;
6. generated PostgreSQL EF migration and Docker Compose assets;
7. deterministic quality PASS and Reviewer approval;
8. persisted audit events and correlation ID;
9. a release ZIP digest and file count without exposing host filesystem paths.

Equivalent API request:

```http
POST /api/v1/projects/run
Content-Type: application/json
X-API-Key: <configured key, when enabled>
X-Correlation-ID: <optional caller id>
```

```json
{
  "request": "Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports.",
  "target_profile": "enterprise-dotnet-react"
}
```

## Native generated-source verification

Repository CI treats the generated enterprise source as a real build target rather than only inspecting text. The `generated-enterprise-stack` job:

```text
factory generation
  -> governed structural/security validation
  -> dotnet test (generated ASP.NET Core/xUnit solution)
  -> npm install + npm audit --audit-level=moderate
  -> npm run build (generated React/TypeScript application)
```

The enterprise profile is not accepted when any of those gates fail. The generated frontend dependency set is kept above currently known moderate-or-higher npm advisories used by this profile.

For a generated release with a configured identity provider, set `POSTGRES_PASSWORD`, `OIDC_AUTHORITY` and `OIDC_AUDIENCE`, then run:

```bash
docker compose up --build
```

The web container is exposed by the generated compose file; API authorization still requires a valid JWT from the configured OIDC provider.

## Acceptance boundary

`enterprise-dotnet-react` is accepted as the portfolio enterprise vertical slice when all of these are green on `main`:

- factory Ruff/pytest suite;
- Control Center production build;
- enterprise architecture/profile contract tests;
- generated ASP.NET Core restore/build/xUnit tests;
- generated frontend dependency audit at moderate severity or higher;
- generated React/TypeScript production build;
- governed release/security/audit regression tests.

This does not re-label the factory execution plane as an untrusted multi-tenant production sandbox. Durable distributed queues, disposable isolated workers/Kubernetes sandboxing, enterprise tenant entitlements, external secret brokerage, immutable artifact storage and HA platform services remain production-platform evolution items.

## Compatibility

The existing `lightweight-python` profile remains available for deterministic zero-credential demos and regression coverage. The enterprise profile must not weaken the existing governed runtime, security gate, MCP boundary, audit persistence, repair loop or release controls.
