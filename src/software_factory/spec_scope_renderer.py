from __future__ import annotations

import json
import re

from .contracts import GeneratedFile
from .project_model import EnterpriseProjectModel
from .specification import ApplicationSpec, EntityFieldSpec, EntitySpec, PermissionSpec


def _identifier(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    if not parts:
        raise ValueError("Identifier must contain an alphanumeric character")
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _resource_name(entity_name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", entity_name).lower()


def _field(entity: EntitySpec, name: str) -> EntityFieldSpec:
    for field in entity.fields:
        if field.name == name:
            return field
    raise ValueError(f"Unknown field {entity.name}.{name}")


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


def _binding_field(permission: PermissionSpec, entity: EntitySpec) -> EntityFieldSpec:
    binding = permission.scope_binding
    if binding is None:
        raise ValueError(
            f"Scoped permission has no binding: {permission.role}/{permission.resource}"
        )
    if binding.entity != entity.name:
        raise ValueError(
            f"Permission resource binding does not target {entity.name}: {permission.resource}"
        )
    return _field(entity, binding.record_field)


def _claim_source(permission: PermissionSpec, entity: EntitySpec) -> str:
    binding = permission.scope_binding
    if binding is None:
        raise ValueError(
            f"Scoped permission has no binding: {permission.role}/{permission.resource}"
        )
    field = _binding_field(permission, entity)
    method = _claim_values_method(field)
    return f'{method}(user, {json.dumps(binding.claim_type)})'


def _contains_expression(field: EntityFieldSpec, item_name: str, claims_name: str) -> str:
    field_source = f"{item_name}.{field.name}"
    nullable = field.nullable or not field.required
    if nullable and field.data_type in {"uuid", "integer"}:
        return f"{field_source}.HasValue && {claims_name}.Contains({field_source}.Value)"
    if nullable and field.data_type == "string":
        return f"{field_source} is not null && {claims_name}.Contains({field_source})"
    return f"{claims_name}.Contains({field_source})"


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
    scoped_index = 0
    for permission in permissions:
        if permission.scope == "all":
            continue
        field = _binding_field(permission, entity)
        claims_name = f"scopeValues{scoped_index}"
        expression = _contains_expression(field, "item", claims_name)
        lines.extend(
            [
                f'        if (user.IsInRole("{permission.role}"))',
                "        {",
                f"            var {claims_name} = {_claim_source(permission, entity)};",
                f"            filtered = filtered.Concat(source.Where(item => {expression}));",
                "        }",
            ]
        )
        scoped_index += 1
    lines.extend(["        return filtered.Distinct();", "    }"])
    return "\n".join(lines)


def _ensure_method(entity: EntitySpec, action: str, permissions: list[PermissionSpec]) -> str:
    method = f"Ensure{entity.name}{_identifier(action)}Scope"
    lines = [
        f"    public static void {method}({entity.name} item, ClaimsPrincipal user)",
        "    {",
    ]
    scoped_index = 0
    for permission in permissions:
        role_guard = f'user.IsInRole("{permission.role}")'
        if permission.scope == "all":
            lines.append(f"        if ({role_guard}) return;")
            continue
        field = _binding_field(permission, entity)
        claims_name = f"scopeValues{scoped_index}"
        expression = _contains_expression(field, "item", claims_name)
        lines.extend(
            [
                f"        if ({role_guard})",
                "        {",
                f"            var {claims_name} = {_claim_source(permission, entity)};",
                f"            if ({expression}) return;",
                "        }",
            ]
        )
        scoped_index += 1
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
