# Enterprise .NET + React Generation Profile

`enterprise-dotnet-react` is the production-oriented generation target for business applications that need explicit roles, multi-page navigation, backend-enforced business rules and durable relational persistence.

## Target stack

- React + TypeScript frontend
- ASP.NET Core Web API backend
- PostgreSQL persistence
- EF Core migrations by default; Dapper may be selected for explicit query-heavy read paths
- Docker Compose for local integration
- backend and frontend tests focused on acceptance criteria and critical business rules

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

ASP.NET Core must enforce identity, authorization and business rules server-side. PostgreSQL constraints are used where a rule can be safely expressed at the data layer, but domain/application rules remain explicit in backend code and tests.

## Initial reference scenario

The first accepted enterprise scenario remains Leave Management:

- Employee: create and view own leave requests.
- Manager: view team approval queue and approve/reject pending requests.
- HR: view organization-wide reporting and administrative data.

Representative rules include:

- end date must not precede start date;
- only pending requests can be approved or rejected;
- an employee cannot approve their own request;
- leave requests must not overlap an existing approved request for the same employee;
- approved requests cannot be edited through the normal employee workflow.

The exact rules are represented as structured `BusinessRuleSpec` records before code generation. The generated backend must implement them and QA must derive focused tests from the same specification.

## Compatibility

The existing `lightweight-python` profile remains available for deterministic zero-credential demos and regression coverage. Adding this profile must not weaken the existing governed runtime, security gate, MCP boundary, audit persistence, repair loop or release controls.
