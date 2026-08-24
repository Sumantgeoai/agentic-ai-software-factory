# Generic Dynamic Factory Acceptance

The enterprise generator is considered domain-agnostic only when application source is derived from the validated `ApplicationSpec`, not from a domain-specific source template.

## Supported generic scope

The target is enterprise CRUD/workflow/business-rule applications with:

- arbitrary product names;
- arbitrary role sets and own/team/all permissions;
- multiple entities and typed fields;
- role-aware pages and routes;
- explicit workflows;
- typed custom entity actions and field mutations;
- typed backend-enforced business rules bound to explicit operation/action IDs;
- explicit record-field-to-identity-claim bindings for own/team scopes;
- ASP.NET Core + PostgreSQL backend generation;
- React + TypeScript multi-page frontend generation;
- xUnit and frontend build validation;
- Docker Compose and governed release packaging.

This does not claim that a deterministic compiler can invent arbitrary bespoke algorithms, scientific models or unknown external integrations. Those require LLM/tool planning plus explicit capabilities.

## Probabilistic/deterministic boundary

For the enterprise profile, LLM reasoning ends at the validated requirements, architecture, `ApplicationSpec` and delivery plan. Specialist source artifacts are compiled deterministically from that contract. The LLM does not get unrestricted authority to emit backend authorization or business-rule source code after the specification is accepted.

An enterprise `PermissionSpec` using `own` or `team` scope must identify:

- the entity being protected;
- the record field that carries the ownership/team identifier;
- the JWT/OIDC claim type whose values define the caller's allowed scope.

Generated read queries apply the scope before materialization. Generated create/update/delete/custom-action endpoints enforce the same scope server-side. `all` remains role-authorized but unfiltered. Generic update generation does not overwrite identifiers, scope-binding fields or fields reserved for declared custom actions; sensitive transitions must be modeled explicitly.

Enterprise `BusinessRuleSpec.condition` uses a typed comparison expression with field/literal operands and a constrained operator set. Free-form condition strings are rejected for the enterprise profile. `applies_to` binds each rule to exact CRUD operations or declared action IDs, so source generation never infers enforcement from prose in a trigger description.

`EntityActionSpec` models non-CRUD workflow operations such as approve, reject or assign. An action declares its authorization action and one or more typed field mutations. Mutations can assign a literal or a typed request input. The compiler generates the endpoint, request record when required, row-scope authorization, precondition rule calls and persistence update from the same specification.

## Hardcoding rule

Domain words such as Leave, Complaint or Inspection may exist in acceptance fixtures and generated output for those scenarios. They must not control the generic generator implementation.

The same generator code must build at least these independent scenarios:

1. Leave Management: typed approve/reject actions;
2. Citizen Complaint Portal: typed supervisor assignment action with a request payload;
3. Asset Inspection Manager: typed approve/reject review actions.

Each scenario must produce different namespaces, project/package names, entities, roles, routes, rule metadata, workflow actions and row-scope claim bindings from its own `ApplicationSpec`.

## Legacy template retirement

The runtime enterprise path must not import or depend on the earlier Leave-specific enterprise fixture, authorization, policy or stack template modules. Structured LLM access is separated from deterministic fixtures, and the normal `fixture` provider resolves an enterprise scenario to an independent `ApplicationSpec` before invoking the same generic compiler used by the live-model path.

The `lightweight-python` fixture remains an isolated compatibility/regression profile. It fails closed if it is accidentally asked to satisfy an `enterprise-dotnet-react` request, preventing the lightweight Leave demo from silently becoming the enterprise source path.

## Completion gate

Generic acceptance requires all three scenarios to pass the same pipeline:

`ApplicationSpec -> deterministic specialist compilation -> security gate -> materialization -> dotnet test -> frontend audit/build -> reviewer -> release manifest`

The existing governed runtime, MCP boundary, audit persistence, repair loop, API security and observability remain mandatory and must not be weakened by generic generation.
