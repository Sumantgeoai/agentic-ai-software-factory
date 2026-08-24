from __future__ import annotations

import json
import re

from .contracts import GeneratedFile
from .project_model import EnterpriseProjectModel
from .specification import (
    ApplicationSpec,
    BusinessRuleSpec,
    EntityFieldSpec,
    EntitySpec,
    PermissionSpec,
    RuleConditionSpec,
    RuleOperandSpec,
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


def _id_field(entity: EntitySpec) -> EntityFieldSpec:
    for field in entity.fields:
        if field.name == "Id":
            return field
    raise ValueError(f"Generic CRUD entity requires an Id field: {entity.name}")


def _field(entity: EntitySpec, name: str) -> EntityFieldSpec:
    for field in entity.fields:
        if field.name == name:
            return field
    raise ValueError(f"Unknown field {entity.name}.{name}")


def _rule_method(rule: BusinessRuleSpec) -> str:
    return f"Ensure{_identifier(rule.id)}"


def _typed_condition(rule: BusinessRuleSpec) -> RuleConditionSpec:
    if isinstance(rule.condition, str):
        raise ValueError(f"Enterprise rule requires typed condition: {rule.id}")
    return rule.condition


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
    raise ValueError(f"Unsupported rule literal type: {field.data_type}")


def _operand_source(operand: RuleOperandSpec, entity: EntitySpec, other: RuleOperandSpec) -> tuple[str, EntityFieldSpec]:
    if operand.field is not None:
        field = _field(entity, operand.field)
        return f"item.{field.name}", field
    if other.field is None:
        raise ValueError("Business-rule comparison must reference at least one entity field")
    field = _field(entity, other.field)
    return _csharp_literal(operand.value, field), field


def _condition_source(rule: BusinessRuleSpec, entity: EntitySpec) -> str:
    condition = _typed_condition(rule)
    left_source, left_type = _operand_source(condition.left, entity, condition.right)
    right_source, right_type = _operand_source(condition.right, entity, condition.left)
    if left_type.data_type != right_type.data_type:
        raise ValueError(
            f"Rule operands use incompatible field types for {rule.id}: "
            f"{left_type.data_type}/{right_type.data_type}"
        )
    operator = condition.operator
    if operator in {"eq", "ne"}:
        if left_type.data_type in {"string", "enum"}:
            comparison = (
                f"string.Equals({left_source}, {right_source}, "
                "StringComparison.OrdinalIgnoreCase)"
            )
        else:
            comparison = f"{left_source} == {right_source}"
        return f"!({comparison})" if operator == "ne" else comparison
    if left_type.data_type in {"string", "enum", "boolean", "uuid"}:
        raise ValueError(
            f"Relational operator {operator} is not supported for {left_type.data_type}: {rule.id}"
        )
    symbols = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
    return f"{left_source} {symbols[operator]} {right_source}"


def render_business_rules(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    entities = {entity.name: entity for entity in spec.entities}
    methods: list[str] = []
    for rule in spec.business_rules:
        entity = entities[rule.entity]
        allowed = " || ".join(f'user.IsInRole("{role}")' for role in rule.allowed_roles)
        role_guard = "true" if not allowed else allowed
        comparison = _condition_source(rule, entity)
        methods.append(
            f'''    public static void {_rule_method(rule)}({entity.name} item, ClaimsPrincipal user)
    {{
        if (!({role_guard}))
            throw new BusinessRuleException("{rule.error_code}", "Role is not allowed to execute this rule.");
        if (!({comparison}))
            throw new BusinessRuleException("{rule.error_code}", {json.dumps(rule.description)});
    }}'''
        )
    body = "\n\n".join(methods) or "    // No backend business rules were declared."
    content = f'''using System.Security.Claims;

namespace {model.root_namespace}.Domain;

public sealed class BusinessRuleException(string code, string message) : Exception(message)
{{
    public string Code {{ get; }} = code;
}}

public static class BusinessRules
{{
{body}
}}
'''
    return GeneratedFile(path=model.api_path("Domain/BusinessRules.cs"), content=content)


def _claim_values_method(field: EntityFieldSpec) -> str:
    return {
        "uuid": "GuidClaims",
        "string": "StringClaims",
        "integer": "IntClaims",
    }[field.data_type]


def _permissions_for(
    spec: ApplicationSpec,
    entity: EntitySpec,
    action: str,
) -> list[PermissionSpec]:
    resource = _resource_name(entity.name)
    return [
        permission
        for permission in spec.permissions
        if permission.resource == resource and action in permission.actions
    ]


def _scope_expression(permission: PermissionSpec, entity: EntitySpec, item_name: str) -> str:
    if permission.scope == "all":
        return "true"
    binding = permission.scope_binding
    if binding is None:
        raise ValueError(
            f"Scoped permission has no binding: {permission.role}/{permission.resource}"
        )
    if binding.entity != entity.name:
        raise ValueError(
            f"Permission resource binding does not target {entity.name}: {permission.resource}"
        )
    field = _field(entity, binding.record_field)
    method = _claim_values_method(field)
    return f'{method}(user, {json.dumps(binding.claim_type)}).Contains({item_name}.{field.name})'


def _filter_method(entity: EntitySpec, action: str, permissions: list[PermissionSpec]) -> str:
    method = f"Filter{entity.name}{_identifier(action)}"
    all_roles = [permission.role for permission in permissions if permission.scope == "all"]
    all_guard = " || ".join(f'user.IsInRole("{role}")' for role in all_roles)
    lines = [
        f"    public static IQueryable<{entity.name}> {method}(IQueryable<{entity.name}> source, ClaimsPrincipal user)",
        "    {",
    ]
    if all_guard:
        lines.append(f"        if ({all_guard}) return source;")
    lines.append(f"        IQueryable<{entity.name}> filtered = source.Where(_ => false);")
    for permission in permissions:
        if permission.scope == "all":
            continue
        expression = _scope_expression(permission, entity, "item")
        lines.extend(
            [
                f'        if (user.IsInRole("{permission.role}"))',
                f"            filtered = filtered.Concat(source.Where(item => {expression}));",
            ]
        )
    lines.extend(["        return filtered.Distinct();", "    }"])
    return "\n".join(lines)


def _ensure_method(entity: EntitySpec, action: str, permissions: list[PermissionSpec]) -> str:
    method = f"Ensure{entity.name}{_identifier(action)}Scope"
    lines = [
        f"    public static void {method}({entity.name} item, ClaimsPrincipal user)",
        "    {",
    ]
    for permission in permissions:
        role_guard = f'user.IsInRole("{permission.role}")'
        if permission.scope == "all":
            lines.append(f"        if ({role_guard}) return;")
            continue
        expression = _scope_expression(permission, entity, "item")
        lines.append(f"        if ({role_guard} && {expression}) return;")
    lines.extend(
        [
            f'        throw new ResourceScopeException("SCOPE_FORBIDDEN", "Caller is outside the {entity.name} {action} scope.");',
            "    }",
        ]
    )
    return "\n".join(lines)


def render_resource_scopes(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    methods: list[str] = []
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
            permissions = _permissions_for(spec, entity, action)
            if action == "read":
                methods.append(_filter_method(entity, action, permissions))
            else:
                methods.append(_ensure_method(entity, action, permissions))
    body = "\n\n".join(methods) or "    // No entity-scoped permissions were declared."
    content = f'''using System.Security.Claims;
using {model.root_namespace}.Domain;

namespace {model.root_namespace}.Authorization;

public sealed class ResourceScopeException(string code, string message) : Exception(message)
{{
    public string Code {{ get; }} = code;
}}

public static class ResourceScopes
{{
    private static Guid[] GuidClaims(ClaimsPrincipal user, string claimType) =>
        user.FindAll(claimType)
            .Select(claim => Guid.TryParse(claim.Value, out var value) ? (Guid?)value : null)
            .Where(value => value.HasValue)
            .Select(value => value!.Value)
            .ToArray();

    private static int[] IntClaims(ClaimsPrincipal user, string claimType) =>
        user.FindAll(claimType)
            .Select(claim => int.TryParse(claim.Value, out var value) ? (int?)value : null)
            .Where(value => value.HasValue)
            .Select(value => value!.Value)
            .ToArray();

    private static string[] StringClaims(ClaimsPrincipal user, string claimType) =>
        user.FindAll(claimType).Select(claim => claim.Value).ToArray();

{body}
}}
'''
    return GeneratedFile(path=model.api_path("Authorization/ResourceScopes.cs"), content=content)


def _policy_name(entity: EntitySpec, action: str) -> str:
    return f"{entity.name}{_identifier(action)}"


def _roles_for(spec: ApplicationSpec, entity: EntitySpec, action: str) -> list[str]:
    return [permission.role for permission in _permissions_for(spec, entity, action)]


def render_secured_program(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    policies: list[str] = []
    endpoints: list[str] = []
    rules_by_entity: dict[str, list[BusinessRuleSpec]] = {}
    for rule in spec.business_rules:
        rules_by_entity.setdefault(rule.entity, []).append(rule)

    for entity in spec.entities:
        id_field = _id_field(entity)
        id_type = _CSHARP_TYPES[id_field.data_type]
        route = _table_name(entity.name).replace("_", "-")
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
            if not roles:
                continue
            role_args = ", ".join(json.dumps(role) for role in roles)
            policies.append(
                f'    options.AddPolicy("{_policy_name(entity, action)}", policy => policy.RequireRole({role_args}));'
            )

        if "read" in actions:
            endpoints.append(
                f'''app.MapGet("/api/{route}", async (ClaimsPrincipal user, AppDbContext db) =>
    Results.Ok(await ResourceScopes.Filter{entity.name}Read(db.{entity.name}Set.AsNoTracking(), user).ToListAsync()))
    .RequireAuthorization("{_policy_name(entity, 'read')}");'''
            )

        if "create" in actions:
            guards = [f"ResourceScopes.Ensure{entity.name}CreateScope(item, user);"]
            guards.extend(
                f"BusinessRules.{_rule_method(rule)}(item, user);"
                for rule in rules_by_entity.get(entity.name, [])
                if "create" in rule.trigger.lower()
            )
            guard_source = "\n        ".join(guards)
            endpoints.append(
                f'''app.MapPost("/api/{route}", async ({entity.name} item, ClaimsPrincipal user, AppDbContext db) =>
{{
        {guard_source}
        db.{entity.name}Set.Add(item);
        await db.SaveChangesAsync();
        return Results.Created("/api/{route}", item);
}}).RequireAuthorization("{_policy_name(entity, 'create')}");'''
            )

        if "update" in actions:
            guards = [f"ResourceScopes.Ensure{entity.name}UpdateScope(existing, user);"]
            guards.extend(
                f"BusinessRules.{_rule_method(rule)}(existing, user);"
                for rule in rules_by_entity.get(entity.name, [])
                if "update" in rule.trigger.lower()
            )
            guard_source = "\n        ".join(guards)
            endpoints.append(
                f'''app.MapPut("/api/{route}/{{id}}", async ({id_type} id, {entity.name} item, ClaimsPrincipal user, AppDbContext db) =>
{{
        var existing = await db.{entity.name}Set.FindAsync(id);
        if (existing is null) return Results.NotFound();
        {guard_source}
        db.Entry(existing).CurrentValues.SetValues(item);
        await db.SaveChangesAsync();
        return Results.Ok(existing);
}}).RequireAuthorization("{_policy_name(entity, 'update')}");'''
            )

        has_status = any(field.name == "Status" for field in entity.fields)
        for action, target_status in (("approve", "Approved"), ("reject", "Rejected")):
            if action not in actions or not has_status:
                continue
            guards = [f"ResourceScopes.Ensure{entity.name}{_identifier(action)}Scope(existing, user);"]
            guards.extend(
                f"BusinessRules.{_rule_method(rule)}(existing, user);"
                for rule in rules_by_entity.get(entity.name, [])
                if action in rule.trigger.lower() or "approve or reject" in rule.trigger.lower()
            )
            guard_source = "\n        ".join(guards)
            endpoints.append(
                f'''app.MapPost("/api/{route}/{{id}}/{action}", async ({id_type} id, ClaimsPrincipal user, AppDbContext db) =>
{{
        var existing = await db.{entity.name}Set.FindAsync(id);
        if (existing is null) return Results.NotFound();
        {guard_source}
        existing.Status = "{target_status}";
        await db.SaveChangesAsync();
        return Results.Ok(existing);
}}).RequireAuthorization("{_policy_name(entity, action)}");'''
            )

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
'''
    return GeneratedFile(path=model.api_path("Program.cs"), content=content)


def _alternate_literal(value: object, field: EntityFieldSpec) -> object:
    if field.data_type in {"string", "enum"}:
        return "__different__" if value != "__different__" else "__other__"
    if field.data_type == "integer":
        return int(value) + 1
    if field.data_type == "decimal":
        return float(value) + 1
    if field.data_type == "boolean":
        return not bool(value)
    if field.data_type == "uuid":
        return "00000000-0000-0000-0000-000000000002"
    return value


def _test_initializers(rule: BusinessRuleSpec, entity: EntitySpec) -> tuple[str, str]:
    condition = _typed_condition(rule)
    if condition.left.field is None or condition.right.value is None:
        return "", ""
    field = _field(entity, condition.left.field)
    if condition.operator not in {"eq", "ne"}:
        return "", ""
    literal = condition.right.value
    different = _alternate_literal(literal, field)
    valid_value = literal if condition.operator == "eq" else different
    invalid_value = different if condition.operator == "eq" else literal
    return (
        f"{field.name} = {_csharp_literal(valid_value, field)}",
        f"{field.name} = {_csharp_literal(invalid_value, field)}",
    )


def render_rule_tests(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    entities = {entity.name: entity for entity in spec.entities}
    tests: list[str] = []
    for index, rule in enumerate(spec.business_rules):
        entity = entities[rule.entity]
        method = _rule_method(rule)
        valid_initializer, invalid_initializer = _test_initializers(rule, entity)
        if valid_initializer and invalid_initializer:
            role = rule.allowed_roles[0] if rule.allowed_roles else spec.roles[0].name
            tests.append(
                f'''    [Fact]
    public void Rule{index + 1}_{_identifier(rule.id)}_enforces_typed_condition()
    {{
        var user = User("{role}");
        var invalid = new {entity.name} {{ {invalid_initializer} }};
        var valid = new {entity.name} {{ {valid_initializer} }};
        var error = Assert.Throws<BusinessRuleException>(() => BusinessRules.{method}(invalid, user));
        Assert.Equal("{rule.error_code}", error.Code);
        BusinessRules.{method}(valid, user);
    }}'''
            )
        else:
            denied_role = "__unauthorized__"
            tests.append(
                f'''    [Fact]
    public void Rule{index + 1}_{_identifier(rule.id)}_fails_closed_for_unauthorized_role()
    {{
        var error = Assert.Throws<BusinessRuleException>(() => BusinessRules.{method}(new {entity.name}(), User("{denied_role}")));
        Assert.Equal("{rule.error_code}", error.Code);
    }}'''
            )
    body = "\n\n".join(tests) or "    [Fact]\n    public void No_rules_declared() => Assert.True(true);"
    content = f'''using System.Security.Claims;
using {model.root_namespace}.Domain;

namespace {model.test_project};

public sealed class BusinessRuleTests
{{
    private static ClaimsPrincipal User(string role) => new(
        new ClaimsIdentity(new[] {{ new Claim(ClaimTypes.Role, role) }}, "test"));

{body}
}}
'''
    return GeneratedFile(path=model.test_path("BusinessRuleTests.cs"), content=content)


def render_scope_tests(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    cases: list[str] = []
    for entity in spec.entities:
        for action in sorted(
            {
                action
                for permission in spec.permissions
                if permission.resource == _resource_name(entity.name) and permission.scope != "all"
                for action in permission.actions
                if action != "read"
            }
        ):
            permission = next(
                p
                for p in _permissions_for(spec, entity, action)
                if p.scope != "all" and p.scope_binding is not None
            )
            binding = permission.scope_binding
            assert binding is not None
            field = _field(entity, binding.record_field)
            if field.data_type != "uuid":
                continue
            method = f"Ensure{entity.name}{_identifier(action)}Scope"
            cases.append(
                f'''    [Fact]
    public void {method}_rejects_record_outside_claim_scope()
    {{
        var userId = Guid.Parse("00000000-0000-0000-0000-000000000001");
        var otherId = Guid.Parse("00000000-0000-0000-0000-000000000002");
        var user = User("{permission.role}", "{binding.claim_type}", userId.ToString());
        var item = new {entity.name} {{ {field.name} = otherId }};
        Assert.Throws<ResourceScopeException>(() => ResourceScopes.{method}(item, user));
        item.{field.name} = userId;
        ResourceScopes.{method}(item, user);
    }}'''
            )
    body = "\n\n".join(cases) or "    [Fact]\n    public void No_scoped_write_rules_declared() => Assert.True(true);"
    content = f'''using System.Security.Claims;
using {model.root_namespace}.Authorization;
using {model.root_namespace}.Domain;

namespace {model.test_project};

public sealed class ResourceScopeTests
{{
    private static ClaimsPrincipal User(string role, string claimType, string claimValue) => new(
        new ClaimsIdentity(new[]
        {{
            new Claim(ClaimTypes.Role, role),
            new Claim(claimType, claimValue),
        }}, "test"));

{body}
}}
'''
    return GeneratedFile(path=model.test_path("ResourceScopeTests.cs"), content=content)
