# Generic Dynamic Factory Acceptance

The enterprise generator is considered domain-agnostic only when application source is derived from the validated `ApplicationSpec`, not from a domain-specific source template.

## Supported generic scope

The target is enterprise CRUD/workflow/business-rule applications with:

- arbitrary product names;
- arbitrary role sets and own/team/all permissions;
- multiple entities and typed fields;
- role-aware pages and routes;
- explicit workflows;
- structured backend-enforced business rules;
- ASP.NET Core + PostgreSQL backend generation;
- React + TypeScript multi-page frontend generation;
- xUnit and frontend build validation;
- Docker Compose and governed release packaging.

This does not claim that a deterministic template engine can invent arbitrary bespoke algorithms, scientific models or unknown external integrations. Those require LLM/tool planning plus explicit capabilities.

## Hardcoding rule

Domain words such as Leave, Complaint or Inspection may exist in acceptance fixtures and generated output for those scenarios. They must not control the generic generator implementation.

The same generator code must build at least these independent scenarios:

1. Leave Management;
2. Citizen Complaint Portal;
3. Asset Inspection Manager.

Each scenario must produce different namespaces, project/package names, entities, roles, routes and rule metadata from its own `ApplicationSpec`.

## Completion gate

Generic acceptance requires all three scenarios to pass the same pipeline:

`ApplicationSpec -> specialist generation -> security gate -> materialization -> dotnet test -> frontend audit/build -> reviewer -> release manifest`

The existing governed runtime, MCP boundary, audit persistence, repair loop, API security and observability remain mandatory and must not be weakened by generic generation.
