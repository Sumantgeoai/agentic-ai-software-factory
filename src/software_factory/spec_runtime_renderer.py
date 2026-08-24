from __future__ import annotations

import json
import re

from .contracts import CodeBundle, GeneratedFile, RequirementSpec
from .project_model import EnterpriseProjectModel
from .spec_renderer import render_enterprise_bundle
from .specification import ApplicationSpec, BusinessRuleSpec, EntityFieldSpec, EntitySpec


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

_PG_TYPES = {
    "string": "text",
    "integer": "integer",
    "decimal": "numeric",
    "boolean": "boolean",
    "date": "date",
    "datetime": "timestamp with time zone",
    "uuid": "uuid",
    "enum": "text",
}

_SIMPLE_RULE = re.compile(
    r"^(?P<field>[A-Za-z][A-Za-z0-9_]*)\s*(?P<operator>==|!=)\s*(?P<value>[A-Za-z0-9_-]+)$"
)


def _identifier(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    if not parts:
        raise ValueError("Identifier must contain an alphanumeric character")
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _resource_name(entity_name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", entity_name).lower()


def _table_name(entity_name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", entity_name).lower() + "s"


def _replace(files: list[GeneratedFile], replacement: GeneratedFile) -> None:
    for index, item in enumerate(files):
        if item.path == replacement.path:
            files[index] = replacement
            return
    files.append(replacement)


def _roles_for(spec: ApplicationSpec, resource: str, action: str) -> list[str]:
    roles: list[str] = []
    for permission in spec.permissions:
        if permission.resource == resource and action in permission.actions:
            if permission.role not in roles:
                roles.append(permission.role)
    return roles


def _id_field(entity: EntitySpec) -> EntityFieldSpec:
    for field in entity.fields:
        if field.name == "Id":
            return field
    raise ValueError(f"Generic CRUD entity requires an Id field: {entity.name}")


def _rule_method(rule: BusinessRuleSpec) -> str:
    return f"Ensure{_identifier(rule.id)}"


def _parse_rule(rule: BusinessRuleSpec, entity: EntitySpec) -> tuple[EntityFieldSpec, str, str]:
    match = _SIMPLE_RULE.fullmatch(rule.condition.strip())
    if match is None:
        raise ValueError(
            f"Unsupported deterministic business-rule condition for {rule.id}: {rule.condition}"
        )
    fields = {field.name: field for field in entity.fields}
    field = fields.get(match.group("field"))
    if field is None:
        raise ValueError(f"Unknown business-rule field for {rule.id}: {match.group('field')}")
    if field.data_type not in {"string", "enum"}:
        raise ValueError(
            f"Deterministic rule grammar currently supports string/enum comparisons: {rule.id}"
        )
    return field, match.group("operator"), match.group("value")


def _business_rules(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    entities = {entity.name: entity for entity in spec.entities}
    methods: list[str] = []
    for rule in spec.business_rules:
        entity = entities[rule.entity]
        field, operator, value = _parse_rule(rule, entity)
        allowed = " || ".join(f'user.IsInRole("{role}")' for role in rule.allowed_roles)
        role_guard = "true" if not allowed else allowed
        comparison = (
            f'string.Equals(item.{field.name}, "{value}", StringComparison.OrdinalIgnoreCase)'
        )
        if operator == "!=":
            comparison = f"!({comparison})"
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


def _policy_name(entity: EntitySpec, action: str) -> str:
    return f"{entity.name}{_identifier(action)}"


def _secured_program(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    policies: list[str] = []
    endpoint_blocks: list[str] = []
    rules_by_entity: dict[str, list[BusinessRuleSpec]] = {}
    for rule in spec.business_rules:
        rules_by_entity.setdefault(rule.entity, []).append(rule)

    for entity in spec.entities:
        id_field = _id_field(entity)
        id_type = _CSHARP_TYPES[id_field.data_type]
        resource = _resource_name(entity.name)
        route = _table_name(entity.name).replace("_", "-")
        actions = {action for p in spec.permissions if p.resource == resource for action in p.actions}
        for action in sorted(actions):
            roles = _roles_for(spec, resource, action)
            if not roles:
                continue
            role_args = ", ".join(json.dumps(role) for role in roles)
            policies.append(
                f'    options.AddPolicy("{_policy_name(entity, action)}", policy => policy.RequireRole({role_args}));'
            )

        read_roles = _roles_for(spec, resource, "read")
        if read_roles:
            endpoint_blocks.append(
                f'''app.MapGet("/api/{route}", async (AppDbContext db) =>
    Results.Ok(await db.{entity.name}Set.AsNoTracking().ToListAsync()))
    .RequireAuthorization("{_policy_name(entity, 'read')}");'''
            )

        create_roles = _roles_for(spec, resource, "create")
        if create_roles:
            create_rules = [
                rule for rule in rules_by_entity.get(entity.name, []) if "create" in rule.trigger.lower()
            ]
            guards = "\n        ".join(
                f"BusinessRules.{_rule_method(rule)}(item, user);" for rule in create_rules
            )
            if guards:
                guards = "        " + guards + "\n"
            endpoint_blocks.append(
                f'''app.MapPost("/api/{route}", async ({entity.name} item, ClaimsPrincipal user, AppDbContext db) =>
{{
{guards}        db.{entity.name}Set.Add(item);
        await db.SaveChangesAsync();
        return Results.Created("/api/{route}", item);
}}).RequireAuthorization("{_policy_name(entity, 'create')}");'''
            )

        update_roles = _roles_for(spec, resource, "update")
        if update_roles:
            update_rules = [
                rule for rule in rules_by_entity.get(entity.name, []) if "update" in rule.trigger.lower()
            ]
            guards = "\n        ".join(
                f"BusinessRules.{_rule_method(rule)}(existing, user);" for rule in update_rules
            )
            if guards:
                guards += "\n"
            endpoint_blocks.append(
                f'''app.MapPut("/api/{route}/{{id}}", async ({id_type} id, {entity.name} item, ClaimsPrincipal user, AppDbContext db) =>
{{
        var existing = await db.{entity.name}Set.FindAsync(id);
        if (existing is null) return Results.NotFound();
        {guards}db.Entry(existing).CurrentValues.SetValues(item);
        await db.SaveChangesAsync();
        return Results.Ok(existing);
}}).RequireAuthorization("{_policy_name(entity, 'update')}");'''
            )

        has_status = any(field.name == "Status" for field in entity.fields)
        for action, target_status in (("approve", "Approved"), ("reject", "Rejected")):
            roles = _roles_for(spec, resource, action)
            if not roles or not has_status:
                continue
            decision_rules = [
                rule
                for rule in rules_by_entity.get(entity.name, [])
                if action in rule.trigger.lower() or "approve or reject" in rule.trigger.lower()
            ]
            guards = "\n        ".join(
                f"BusinessRules.{_rule_method(rule)}(existing, user);" for rule in decision_rules
            )
            if guards:
                guards += "\n"
            endpoint_blocks.append(
                f'''app.MapPost("/api/{route}/{{id}}/{action}", async ({id_type} id, ClaimsPrincipal user, AppDbContext db) =>
{{
        var existing = await db.{entity.name}Set.FindAsync(id);
        if (existing is null) return Results.NotFound();
        {guards}existing.Status = "{target_status}";
        await db.SaveChangesAsync();
        return Results.Ok(existing);
}}).RequireAuthorization("{_policy_name(entity, action)}");'''
            )

    policy_source = "\n".join(policies)
    endpoints = "\n\n".join(endpoint_blocks)
    content = f'''using System.Security.Claims;
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
{policy_source}
}});

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();

{endpoints}

app.Run();
'''
    return GeneratedFile(path=model.api_path("Program.cs"), content=content)


def _migration(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    blocks: list[str] = []
    downs: list[str] = []
    for entity in spec.entities:
        _id_field(entity)
        columns: list[str] = []
        for field in entity.fields:
            cs_type = _CSHARP_TYPES[field.data_type]
            nullable = field.nullable or not field.required
            columns.append(
                f'                {field.name} = table.Column<{cs_type}>(type: "{_PG_TYPES[field.data_type]}", nullable: {str(nullable).lower()})'
            )
        columns_source = ",\n".join(columns)
        table = _table_name(entity.name)
        blocks.append(
            f'''        migrationBuilder.CreateTable(
            name: "{table}",
            columns: table => new
            {{
{columns_source}
            }},
            constraints: table =>
            {{
                table.PrimaryKey("PK_{table}", x => x.Id);
            }});'''
        )
        downs.append(f'        migrationBuilder.DropTable(name: "{table}");')
    content = f'''using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace {model.root_namespace}.Infrastructure.Migrations;

public partial class Initial : Migration
{{
    protected override void Up(MigrationBuilder migrationBuilder)
    {{
{"\n\n".join(blocks)}
    }}

    protected override void Down(MigrationBuilder migrationBuilder)
    {{
{"\n".join(downs)}
    }}
}}
'''
    return GeneratedFile(
        path=model.api_path("Infrastructure/Migrations/202608240001_Initial.cs"),
        content=content,
    )


def _test_project(model: EnterpriseProjectModel) -> GeneratedFile:
    content = f'''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <IsPackable>false</IsPackable>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.11.1" />
    <PackageReference Include="xunit" Version="2.9.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
  </ItemGroup>
  <ItemGroup><ProjectReference Include="../{model.api_project}/{model.api_project}.csproj" /></ItemGroup>
</Project>
'''
    return GeneratedFile(path=model.test_path(f"{model.test_project}.csproj"), content=content)


def _rule_tests(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    entities = {entity.name: entity for entity in spec.entities}
    tests: list[str] = []
    for index, rule in enumerate(spec.business_rules):
        entity = entities[rule.entity]
        field, operator, value = _parse_rule(rule, entity)
        role = rule.allowed_roles[0] if rule.allowed_roles else spec.roles[0].name
        invalid = "__invalid__" if operator == "==" else value
        valid = value if operator == "==" else "__valid__"
        method = _rule_method(rule)
        tests.append(
            f'''    [Fact]
    public void Rule{index + 1}_{_identifier(rule.id)}_fails_closed()
    {{
        var user = User("{role}");
        var invalid = new {entity.name} {{ {field.name} = "{invalid}" }};
        var valid = new {entity.name} {{ {field.name} = "{valid}" }};
        var error = Assert.Throws<BusinessRuleException>(() => BusinessRules.{method}(invalid, user));
        Assert.Equal("{rule.error_code}", error.Code);
        BusinessRules.{method}(valid, user);
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


def _frontend_bootstrap(requirements: RequirementSpec) -> list[GeneratedFile]:
    return [
        GeneratedFile(
            path="frontend/index.html",
            content=f'''<!doctype html>
<html><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>{requirements.product_name}</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>
''',
        ),
        GeneratedFile(
            path="frontend/src/main.tsx",
            content='''import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
''',
        ),
        GeneratedFile(
            path="frontend/tsconfig.json",
            content='''{"compilerOptions":{"target":"ES2022","useDefineForClassFields":true,"lib":["ES2022","DOM","DOM.Iterable"],"allowJs":false,"skipLibCheck":true,"esModuleInterop":true,"allowSyntheticDefaultImports":true,"strict":true,"forceConsistentCasingInFileNames":true,"module":"ESNext","moduleResolution":"Bundler","resolveJsonModule":true,"isolatedModules":true,"noEmit":true,"jsx":"react-jsx"},"include":["src"]}
''',
        ),
        GeneratedFile(
            path="frontend/vite.config.ts",
            content='''import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({ plugins: [react()] });
''',
        ),
    ]


def _docker_files(model: EnterpriseProjectModel, requirements: RequirementSpec) -> list[GeneratedFile]:
    backend = GeneratedFile(
        path=model.api_path("Dockerfile"),
        content=f'''FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish {model.api_project}.csproj -c Release -o /out --no-self-contained
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /out .
USER 10001
ENTRYPOINT ["dotnet", "{model.api_project}.dll"]
''',
    )
    frontend = GeneratedFile(
        path="frontend/Dockerfile",
        content='''FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --ignore-scripts
COPY . .
RUN npm run build
FROM nginx:1.29-alpine
COPY --from=build /app/dist /usr/share/nginx/html
''',
    )
    compose = GeneratedFile(
        path="docker-compose.yml",
        content=f'''services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
  api:
    build:
      context: ./backend/{model.api_project}
    environment:
      ConnectionStrings__Default: Host=postgres;Database=app;Username=app;Password=${{POSTGRES_PASSWORD}}
    depends_on: [postgres]
  web:
    build:
      context: ./frontend
    ports: ["8080:80"]
''',
    )
    readme = GeneratedFile(
        path="README.generated.md",
        content=f'''# {requirements.product_name}

Generated from the validated ApplicationSpec using the enterprise-dotnet-react profile.

Backend: ASP.NET Core .NET 10. Frontend: React 19 + TypeScript 7. Database: PostgreSQL 16.
Provide external JWT/OIDC configuration before exposing authenticated endpoints.
''',
    )
    return [backend, frontend, compose, readme]


def _python_contract(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    expected_routes = [page.route for page in spec.pages]
    expected_rules = [rule.error_code for rule in spec.business_rules]
    content = f'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_generated_enterprise_contract() -> None:
    program = read({json.dumps(model.api_path('Program.cs'))})
    app = read("frontend/src/App.tsx")
    rules = read({json.dumps(model.api_path('Domain/BusinessRules.cs'))})
    project = read({json.dumps(model.api_path(model.api_project + '.csproj'))})
    assert "net10.0" in project
    assert "UseNpgsql" in program
    assert "RequireAuthorization" in program
    for route in {expected_routes!r}:
        assert f'path="{{route}}"' in app
    for error_code in {expected_rules!r}:
        assert error_code in rules
'''
    return GeneratedFile(path="tests/test_generated_enterprise_contract.py", content=content)


def render_enterprise_runtime_bundle(
    requirements: RequirementSpec,
    spec: ApplicationSpec,
) -> CodeBundle:
    model = EnterpriseProjectModel.from_spec(requirements, spec)
    base = render_enterprise_bundle(requirements, spec)
    files = list(base.files)
    _replace(files, _business_rules(model, spec))
    _replace(files, _secured_program(model, spec))
    _replace(files, _migration(model, spec))
    _replace(files, _test_project(model))
    _replace(files, _rule_tests(model, spec))
    for file in _frontend_bootstrap(requirements):
        _replace(files, file)
    for file in _docker_files(model, requirements):
        _replace(files, file)
    _replace(files, _python_contract(model, spec))
    _replace(
        files,
        GeneratedFile(
            path="application-spec.json",
            content=spec.model_dump_json(indent=2) + "\n",
        ),
    )
    return CodeBundle(files=files)
