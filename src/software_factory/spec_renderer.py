from __future__ import annotations

import json
import re

from .contracts import CodeBundle, GeneratedFile, RequirementSpec
from .project_model import EnterpriseProjectModel
from .specification import ApplicationSpec, EntityFieldSpec


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


def _csharp_type(field: EntityFieldSpec) -> str:
    value = _CSHARP_TYPES[field.data_type]
    nullable = field.nullable or not field.required
    if nullable and value in {"int", "decimal", "bool", "DateOnly", "DateTimeOffset", "Guid"}:
        return f"{value}?"
    if nullable and value == "string":
        return "string?"
    return value


def _entity_source(namespace: str, entity_name: str, fields: list[EntityFieldSpec]) -> str:
    properties = []
    for field in fields:
        csharp_type = _csharp_type(field)
        initializer = " = string.Empty;" if csharp_type == "string" else ""
        properties.append(f"    public {csharp_type} {field.name} {{ get; set; }}{initializer}")
    body = "\n".join(properties)
    return f"""namespace {namespace}.Domain;

public sealed class {entity_name}
{{
{body}
}}
"""


def _api_project(model: EnterpriseProjectModel) -> GeneratedFile:
    return GeneratedFile(
        path=model.api_path(f"{model.api_project}.csproj"),
        content="""<Project Sdk=\"Microsoft.NET.Sdk.Web\">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include=\"Microsoft.AspNetCore.Authentication.JwtBearer\" Version=\"10.0.11\" />
    <PackageReference Include=\"Microsoft.EntityFrameworkCore\" Version=\"10.0.11\" />
    <PackageReference Include=\"Npgsql.EntityFrameworkCore.PostgreSQL\" Version=\"10.0.3\" />
  </ItemGroup>
</Project>
""",
    )


def _db_context(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    dbsets = "\n".join(
        f"    public DbSet<{entity.name}> {entity.name}Set => Set<{entity.name}>();"
        for entity in spec.entities
    )
    tables = "\n".join(
        f'        modelBuilder.Entity<{entity.name}>().ToTable("{_table_name(entity.name)}");'
        for entity in spec.entities
    )
    content = f"""using {model.root_namespace}.Domain;
using Microsoft.EntityFrameworkCore;

namespace {model.root_namespace}.Infrastructure;

public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{{
{dbsets}

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {{
{tables}
    }}
}}
"""
    return GeneratedFile(path=model.api_path("Infrastructure/AppDbContext.cs"), content=content)


def _table_name(entity: str) -> str:
    value = re.sub(r"(?<!^)(?=[A-Z])", "_", entity).lower()
    return f"{value}s"


def _program(model: EnterpriseProjectModel, spec: ApplicationSpec) -> GeneratedFile:
    role_policies = "\n".join(
        f'    options.AddPolicy("Role{_identifier(role.name)}", policy => policy.RequireRole("{role.name}"));'
        for role in spec.roles
    )
    endpoints: list[str] = []
    for entity in spec.entities:
        route = _table_name(entity.name).replace("_", "-")
        endpoints.extend(
            [
                f'app.MapGet("/api/{route}", async (AppDbContext db) => await db.{entity.name}Set.AsNoTracking().ToListAsync());',
                f'app.MapPost("/api/{route}", async ({entity.name} item, AppDbContext db) => {{ db.{entity.name}Set.Add(item); await db.SaveChangesAsync(); return Results.Created($"/api/{route}/{{item.Id}}", item); }});',
            ]
        )
    endpoint_source = "\n".join(endpoints)
    content = f"""using {model.root_namespace}.Domain;
using {model.root_namespace}.Infrastructure;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Default")));
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer();
builder.Services.AddAuthorization(options =>
{{
{role_policies}
}});

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();
{endpoint_source}
app.Run();
"""
    return GeneratedFile(path=model.api_path("Program.cs"), content=content)


def _frontend_package(model: EnterpriseProjectModel) -> GeneratedFile:
    package = {
        "name": model.frontend_package,
        "private": True,
        "version": "1.0.0",
        "type": "module",
        "scripts": {"dev": "vite", "build": "tsc --noEmit && vite build"},
        "dependencies": {
            "react": "19.2.8",
            "react-dom": "19.2.8",
            "react-router-dom": "7.18.2",
        },
        "devDependencies": {
            "@types/react": "19.2.18",
            "@types/react-dom": "19.2.4",
            "@vitejs/plugin-react": "6.1.0",
            "typescript": "7.0.2",
            "vite": "8.1.0",
        },
    }
    return GeneratedFile(path="frontend/package.json", content=json.dumps(package, indent=2) + "\n")


def _frontend_app(requirements: RequirementSpec, spec: ApplicationSpec) -> GeneratedFile:
    roles = ", ".join(json.dumps(role.name) for role in spec.roles)
    nav_items = "\n".join(
        f'      {{role === {json.dumps(page.allowed_roles[0])} || {json.dumps(page.allowed_roles)}.includes(role) ? <NavLink to={json.dumps(page.route)}>{page.title}</NavLink> : null}}'
        for page in spec.pages
    )
    routes = "\n".join(
        f'      <Route path={json.dumps(page.route)} element={{<Page title={json.dumps(page.title)} />}} />'
        for page in spec.pages
    )
    content = f'''import {{ useState }} from "react";
import {{ BrowserRouter, NavLink, Route, Routes }} from "react-router-dom";

const roles = [{roles}] as const;
type Role = (typeof roles)[number];

function Page({{ title }}: {{ title: string }}) {{
  return <section><h2>{{title}}</h2><p>Generated from the application specification.</p></section>;
}}

export function App() {{
  const [role, setRole] = useState<Role>(roles[0]);
  return <BrowserRouter><main>
    <header><h1>{requirements.product_name}</h1><select value={{role}} onChange={{event => setRole(event.target.value as Role)}}>{{roles.map(item => <option key={{item}} value={{item}}>{{item}}</option>)}}</select></header>
    <nav>
{nav_items}
    </nav>
    <Routes>
{routes}
    </Routes>
  </main></BrowserRouter>;
}}
'''
    return GeneratedFile(path="frontend/src/App.tsx", content=content)


def render_enterprise_bundle(
    requirements: RequirementSpec,
    spec: ApplicationSpec,
) -> CodeBundle:
    model = EnterpriseProjectModel.from_spec(requirements, spec)
    files: list[GeneratedFile] = [_api_project(model)]
    for entity in spec.entities:
        files.append(
            GeneratedFile(
                path=model.api_path(f"Domain/{entity.name}.cs"),
                content=_entity_source(model.root_namespace, entity.name, entity.fields),
            )
        )
    files.extend(
        [
            _db_context(model, spec),
            _program(model, spec),
            _frontend_package(model),
            _frontend_app(requirements, spec),
            GeneratedFile(
                path="application-spec.json",
                content=spec.model_dump_json(indent=2) + "\n",
            ),
        ]
    )
    return CodeBundle(files=files)
