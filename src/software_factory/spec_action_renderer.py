from __future__ import annotations

import json
import re

from .contracts import GeneratedFile
from .project_model import EnterpriseProjectModel
from .specification import (
    ApplicationSpec,
    BusinessRuleSpec,
    EntityActionSpec,
    EntityFieldSpec,
    EntitySpec,
    FieldMutationSpec,
)

_CSHARP_TYPES = {
    "string": "string",
    "integer": "int",
    "decimal": "decimal",
    "boolean": "bool",
    "date": "DateOnly",
    "datetime": "DateTimeOffset",
    "uuid": "Guid",
    "enum": "string",
}


def _identifier(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    if not parts:
        raise ValueError("Identifier must contain an alphanumeric character")
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _resource_name(entity_name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", entity_name).lower()


def _table_name(entity_name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", entity_name).lower() + "s"


def _route_name(entity_name: str) -> str:
    return _table_name(entity_name).replace("_", "-")


def _field(entity: EntitySpec, name: str) -> EntityFieldSpec:
    for field in entity.fields:
        if field.name == name:
            return field
    raise ValueError(f"Unknown field {entity.name}.{name}")


def _id_field(entity: EntitySpec) -> EntityFieldSpec:
    return _field(entity, "Id")


def _csharp_type(field: EntityFieldSpec) -> str:
    value = _CSHARP_TYPES[field.data_type]
    nullable = field.nullable or not field.required
    if nullable and value in {"int", "decimal", "bool", "DateOnly", "DateTimeOffset", "Guid"}:
        return f"{value}?"
    if nullable and value == "string":
        return "string?"
    return value


def _csharp_literal(value: object, field: EntityFieldSpec) -> str:
    if field.data_type in {"string", "enum"}:
        if not isinstance(value, str):
            raise ValueError(f"Expected string literal for {field.name}")
        return json.dumps(value)
    if field.data_type == "uuid":
        if not isinstance(value, str):
            raise ValueError(f"Expected UUID string literal for {field.name}")
        return f'Guid.Parse({json.dumps(value)})'
    if field.data_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Expected integer literal for {field.name}")
        return str(value)
    if field.data_type == "decimal":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Expected numeric literal for {field.name}")
        return f"{value}m"
    if field.data_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"Expected boolean literal for {field.name}")
        return str(value).lower()
    if field.data_type == "date":
        if not isinstance(value, str):
            raise ValueError(f"Expected ISO date literal for {field.name}")
        return f'DateOnly.Parse({json.dumps(value)})'
    if field.data_type == "datetime":
        if not isinstance(value, str):
            raise ValueError(f"Expected ISO datetime literal for {field.name}")
        return f'DateTimeOffset.Parse({json.dumps(value)})'
    raise ValueError(f"Unsupported literal type: {field.data_type}")


def _policy_name(entity: EntitySpec, action: str) -> str:
    return f"{entity.name}{_identifier(action)}"


def _rule_method(rule: BusinessRuleSpec) -> str:
    return f"Ensure{_identifier(rule.id)}"


def _rules_for(spec: ApplicationSpec, entity: EntitySpec, operation: str) -> list[BusinessRuleSpec]:
    return [
        rule
        for rule in spec.business_rules
        if rule.entity == entity.name and operation in rule.applies_to
    ]


def _permissions_for(spec: ApplicationSpec, entity: EntitySpec, action: str):
    resource = _resource_name(entity.name)
    return [
        permission
        for permission in spec.permissions
        if permission.resource == resource and action in permission.actions
    ]


def _roles_for(spec: ApplicationSpec, entity: EntitySpec, action: str) -> list[str]:
    return sorted({permission.role for permission in _permissions_for(spec, entity, action)})


def _protected_update_fields(spec: ApplicationSpec, entity: EntitySpec) -> set[str]:
    protected = {"Id"}
    for permission in spec.permissions:
        binding = permission.scope_binding
        if binding is not None and binding.entity == entity.name:
            protected.add(binding.record_field)
    for action in spec.actions:
        if action.entity == entity.name:
            protected.update(mutation.field for mutation in action.mutations)
    return protected


def _rule_calls(spec: ApplicationSpec, entity: EntitySpec, operation: str, item: str) -> list[str]:
    return [
        f"BusinessRules.{_rule_method(rule)}({item}, user);"
        for rule in _rules_for(spec, entity, operation)
    ]


def _render_crud_endpoints(spec: ApplicationSpec, entity: EntitySpec) -> list[str]:
    route = _route_name(entity.name)
    id_field = _id_field(entity)
    id_type = _csharp_type(id_field).removesuffix("?")
    actions = {
        action
        for permission in spec.permissions
        if permission.resource == _resource_name(entity.name)
        for action in permission.actions
    }
    endpoints: list[str] = []

    if "read" in actions:
        endpoints.append(
            f'''app.MapGet("/api/{route}", async (ClaimsPrincipal user, AppDbContext db) =>
    Results.Ok(await ResourceScopes.Filter{entity.name}Read(db.{entity.name}Set.AsNoTracking(), user).ToListAsync()))
    .RequireAuthorization("{_policy_name(entity, 'read')}");'''
        )

    if "create" in actions:
        guards = [f"ResourceScopes.Ensure{entity.name}CreateScope(item, user);"]
        guards.extend(_rule_calls(spec, entity, "create", "item"))
        if id_field.data_type == "uuid":
            guards.append(f"if (item.{id_field.name} == Guid.Empty) item.{id_field.name} = Guid.NewGuid();")
        guard_source = "\n        ".join(guards)
        endpoints.append(
            f'''app.MapPost("/api/{route}", async ({entity.name} item, ClaimsPrincipal user, AppDbContext db) =>
{{
        {guard_source}
        db.{entity.name}Set.Add(item);
        await db.SaveChangesAsync();
        return Results.Created($"/api/{route}/{{item.{id_field.name}}}", item);
}}).RequireAuthorization("{_policy_name(entity, 'create')}");'''
        )

    if "update" in actions:
        guards = [f"ResourceScopes.Ensure{entity.name}UpdateScope(existing, user);"]
        guards.extend(_rule_calls(spec, entity, "update", "existing"))
        assignments = [
            f"existing.{field.name} = item.{field.name};"
            for field in entity.fields
            if field.name not in _protected_update_fields(spec, entity)
        ]
        guard_source = "\n        ".join(guards)
        assignment_source = "\n        ".join(assignments) or "// No mutable fields for generic update."
        endpoints.append(
            f'''app.MapPut("/api/{route}/{{id}}", async ({id_type} id, {entity.name} item, ClaimsPrincipal user, AppDbContext db) =>
{{
        var existing = await db.{entity.name}Set.FindAsync(id);
        if (existing is null) return Results.NotFound();
        {guard_source}
        {assignment_source}
        await db.SaveChangesAsync();
        return Results.Ok(existing);
}}).RequireAuthorization("{_policy_name(entity, 'update')}");'''
        )

    if "delete" in actions:
        guards = [f"ResourceScopes.Ensure{entity.name}DeleteScope(existing, user);"]
        guards.extend(_rule_calls(spec, entity, "delete", "existing"))
        guard_source = "\n        ".join(guards)
        endpoints.append(
            f'''app.MapDelete("/api/{route}/{{id}}", async ({id_type} id, ClaimsPrincipal user, AppDbContext db) =>
{{
        var existing = await db.{entity.name}Set.FindAsync(id);
        if (existing is null) return Results.NotFound();
        {guard_source}
        db.{entity.name}Set.Remove(existing);
        await db.SaveChangesAsync();
        return Results.NoContent();
}}).RequireAuthorization("{_policy_name(entity, 'delete')}");'''
        )
    return endpoints


def _action_request_type(action: EntityActionSpec, entity: EntitySpec) -> tuple[str | None, str | None]:
    inputs: dict[str, EntityFieldSpec] = {}
    for mutation in action.mutations:
        if mutation.source != "input":
            continue
        assert mutation.input_name is not None
        field = _field(entity, mutation.field)
        previous = inputs.get(mutation.input_name)
        if previous is not None and _csharp_type(previous) != _csharp_type(field):
            raise ValueError(
                f"Action input uses incompatible field types: {action.id}/{mutation.input_name}"
            )
        inputs[mutation.input_name] = field
    if not inputs:
        return None, None
    type_name = f"{_identifier(action.id)}{entity.name}Request"
    parameters = ", ".join(
        f"{_csharp_type(field)} {input_name}" for input_name, field in sorted(inputs.items())
    )
    return type_name, f"public sealed record {type_name}({parameters});"


def _mutation_source(action: EntityActionSpec, entity: EntitySpec) -> list[str]:
    lines: list[str] = []
    for mutation in action.mutations:
        field = _field(entity, mutation.field)
        if mutation.source == "literal":
            lines.append(f"existing.{field.name} = {_csharp_literal(mutation.value, field)};")
        else:
            assert mutation.input_name is not None
            lines.append(f"existing.{field.name} = payload.{mutation.input_name};")
    return lines


def _render_custom_action(
    spec: ApplicationSpec,
    action: EntityActionSpec,
    entity: EntitySpec,
) -> tuple[str, str | None]:
    route = _route_name(entity.name)
    id_type = _csharp_type(_id_field(entity)).removesuffix("?")
    request_type, request_declaration = _action_request_type(action, entity)
    payload_parameter = f", {request_type} payload" if request_type is not None else ""
    guards = [
        f"ResourceScopes.Ensure{entity.name}{_identifier(action.permission_action)}Scope(existing, user);"
    ]
    guards.extend(_rule_calls(spec, entity, action.id, "existing"))
    guard_source = "\n        ".join(guards)
    mutation_source = "\n        ".join(_mutation_source(action, entity))
    endpoint = f'''app.MapPost("/api/{route}/{{id}}/{action.id}", async ({id_type} id{payload_parameter}, ClaimsPrincipal user, AppDbContext db) =>
{{
        var existing = await db.{entity.name}Set.FindAsync(id);
        if (existing is null) return Results.NotFound();
        {guard_source}
        {mutation_source}
        await db.SaveChangesAsync();
        return Results.Ok(existing);
}}).RequireAuthorization("{_policy_name(entity, action.permission_action)}");'''
    return endpoint, request_declaration


def render_application_program(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    entities = {entity.name: entity for entity in spec.entities}
    policies: list[str] = []
    for entity in spec.entities:
        actions = sorted(
            {
                action
                for permission in spec.permissions
                if permission.resource == _resource_name(entity.name)
                for action in permission.actions
            }
        )
        for action in actions:
            roles = _roles_for(spec, entity, action)
            if roles:
                role_args = ", ".join(json.dumps(role) for role in roles)
                policies.append(
                    f'    options.AddPolicy("{_policy_name(entity, action)}", policy => policy.RequireRole({role_args}));'
                )

    endpoints: list[str] = []
    declarations: list[str] = []
    for entity in spec.entities:
        endpoints.extend(_render_crud_endpoints(spec, entity))
    for action in spec.actions:
        endpoint, declaration = _render_custom_action(spec, action, entities[action.entity])
        endpoints.append(endpoint)
        if declaration is not None and declaration not in declarations:
            declarations.append(declaration)

    content = f'''using System.Security.Claims;
using {model.root_namespace}.Authorization;
using {model.root_namespace}.Domain;
using {model.root_namespace}.Infrastructure;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Default")));
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer();
builder.Services.AddAuthorization(options =>
{{
{"\n".join(policies)}
}});

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();
app.Use(async (context, next) =>
{{
    try
    {{
        await next();
    }}
    catch (ResourceScopeException error)
    {{
        context.Response.StatusCode = StatusCodes.Status403Forbidden;
        await Results.Problem(statusCode: 403, title: error.Code, detail: error.Message).ExecuteAsync(context);
    }}
    catch (BusinessRuleException error)
    {{
        context.Response.StatusCode = StatusCodes.Status409Conflict;
        await Results.Problem(statusCode: 409, title: error.Code, detail: error.Message).ExecuteAsync(context);
    }}
}});

{"\n\n".join(endpoints)}

app.Run();

{"\n".join(declarations)}
'''
    return GeneratedFile(path=model.api_path("Program.cs"), content=content)
