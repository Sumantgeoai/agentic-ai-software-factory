# Deployment and Production Boundaries

This repository deliberately separates the runnable portfolio deployment from the controls required for a production software-generation service. The same application code can be promoted, but the execution, identity, persistence and artifact layers must be strengthened as the environment becomes less trusted.

## Environment classes

| Concern | Pilot / local | Staging | Production target |
| --- | --- | --- | --- |
| Model | `fixture` or NVIDIA NIM | NVIDIA NIM | approved managed model gateway with quotas and egress controls |
| API identity | optional API key | required API key behind TLS gateway | enterprise OIDC/service identity at gateway; API key only for service-to-service fallback |
| Run database | SQLite | PostgreSQL | managed PostgreSQL with HA, backups and tested restore |
| Workspace | local named volume | persistent isolated volume | per-run ephemeral isolated executor; API nodes do not execute generated code locally |
| Release storage | workspace ZIP | persistent release volume | immutable object/artifact storage with retention and malware/policy scanning |
| Observability | local spans | OTLP collector | central traces, metrics and logs with correlation IDs and alerting |
| Scale model | one API process | one or a few replicas | stateless API replicas + durable queue + isolated worker pool |
| Network | localhost bind | reverse proxy/private subnet | authenticated gateway, private services, deny-by-default egress |

The current Docker deployment is **pilot/staging acceptable**, not a final multi-tenant production executor. In particular, generated tests still execute inside the API container. Production must move deterministic execution to an isolated worker boundary before accepting untrusted tenant prompts or repositories.

## Local container deployment

Copy `.env.example` to `.env`, set any required secrets, then run:

```bash
docker compose up --build -d
docker compose ps
curl http://127.0.0.1:8080/health
```

The compose file binds the API to loopback by default, runs the application as a non-root user, drops Linux capabilities, enables `no-new-privileges`, keeps the root filesystem read-only, and persists only `/app/workspaces` and `/app/data` in named volumes.

For an authenticated staging run, set at minimum:

```text
SOFTWARE_FACTORY_API_KEY=<secret-from-your-secret-store>
SOFTWARE_FACTORY_MODEL_PROVIDER=nvidia
SOFTWARE_FACTORY_NVIDIA_API_KEY=<nvidia-key>
SOFTWARE_FACTORY_ALLOWED_ORIGINS=https://factory-ui.example.internal
```

Do not commit `.env` or inject an API key into `VITE_*` variables. Vite values are browser-visible. The control center accepts a session-only key for pilot/staging use; in production the browser should authenticate to an enterprise gateway instead.

## PostgreSQL

Set `SOFTWARE_FACTORY_DATABASE_URL` to a PostgreSQL SQLAlchemy URL, for example a secret-managed value with the form:

```text
postgresql+psycopg://<user>:<password>@<host>:5432/<database>
```

Use a dedicated database role with only the permissions required for factory run and audit tables. Production should use TLS to the database, automated backups, point-in-time recovery where available, connection limits, and a restore test. SQLite is intentionally limited to local/pilot operation.

## OpenTelemetry

Set:

```text
OTEL_SERVICE_NAME=agentic-ai-software-factory
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://otel-collector.example.internal/v1/traces
```

HTTP requests and factory runs are traced. `X-Correlation-ID` is validated, returned to the client, attached to spans, and copied into lifecycle audit event payloads. Do not put prompts, API keys, generated source, or model credentials in span attributes.

## API boundary

`/health` is intentionally public and returns only a minimal health state. Factory endpoints under `/api/v1` require `X-API-Key` when `SOFTWARE_FACTORY_API_KEY` is configured.

Current endpoints:

```text
POST /api/v1/projects/run
GET  /api/v1/runs/{project_id}
GET  /api/v1/runs/{project_id}/audit
```

The API key uses constant-time comparison. This is suitable for controlled pilot/staging access over TLS, but it is not user authorization. A production deployment should terminate identity at an authenticated gateway, map the caller to tenant/project entitlements, enforce quotas and request limits there, and pass only trusted service identity to the private API.

## Production execution architecture

The intended production topology is:

```text
Browser / CI client
        |
Authenticated gateway + rate limits + tenant authorization
        |
Stateless Factory API
        |
Durable run queue / scheduler
        |
Isolated execution workers
        |---- egress policy
        |---- CPU / memory / time / file-size quotas
        |---- ephemeral per-run workspace
        |---- deterministic tool allow-list
        |
PostgreSQL audit/run store     Immutable release object store
        |
OpenTelemetry collector -> central observability
```

The LLM continues to produce structured plans and artifacts. It never receives a raw shell. Workers execute only registry-approved tools and commands. A worker should be disposable after each run, and one tenant's workspace must never be mounted into another tenant's execution context.

## Reliability and failure handling

A failed security gate must produce no workspace side effect and no release. A failed compile/test gate may enter the bounded repair loop; every repaired bundle is scanned again before execution. If retries are exhausted, Reviewer must reject release. Database lifecycle transitions and their terminal audit event are committed atomically.

For production, add a durable queue with visibility timeouts or leases so a crashed worker can be retried without duplicating committed side effects. Use the project/run ID plus tool idempotency key as the replay boundary. Release publishing should be content-addressed and atomic: upload under a temporary key, verify digest, then promote the immutable manifest reference.

## Rollback

Application rollback is image-based: retain the previously deployed immutable image digest and redeploy it if a release regresses. Database schema changes should be backward-compatible for at least one application version and applied separately from application rollout. Do not roll back by deleting audit history or generated release evidence.

Before promotion, verify:

```text
1. Backend CI: Ruff and pytest green.
2. Control-center production build green.
3. Health check succeeds through the intended ingress path.
4. API authentication rejects missing/invalid credentials where enabled.
5. Correlation ID is returned and appears in audit events.
6. Security-blocked generation creates no workspace/release.
7. Successful fixture run produces a deterministic release manifest and digest.
8. Database backup/restore and release retention are validated for the target environment.
```
