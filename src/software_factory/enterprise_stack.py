from __future__ import annotations

from .contracts import GeneratedFile

API_PROJECT = GeneratedFile(
    path="backend/LeaveManagement.Api/LeaveManagement.Api.csproj",
    content='''<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Authentication.JwtBearer" Version="10.0.11" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="10.0.11">
      <PrivateAssets>all</PrivateAssets>
      <IncludeAssets>runtime; build; native; contentfiles; analyzers; buildtransitive</IncludeAssets>
    </PackageReference>
    <PackageReference Include="Npgsql.EntityFrameworkCore.PostgreSQL" Version="10.0.3" />
  </ItemGroup>
</Project>
''',
)

TEST_PROJECT = GeneratedFile(
    path="backend/LeaveManagement.Tests/LeaveManagement.Tests.csproj",
    content='''<Project Sdk="Microsoft.NET.Sdk">
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
  <ItemGroup><ProjectReference Include="../LeaveManagement.Api/LeaveManagement.Api.csproj" /></ItemGroup>
</Project>
''',
)

BACKEND_DOCKERFILE = GeneratedFile(
    path="backend/LeaveManagement.Api/Dockerfile",
    content='''FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish LeaveManagement.Api.csproj -c Release -o /out --no-self-contained

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /out .
USER 10001
ENTRYPOINT ["dotnet", "LeaveManagement.Api.dll"]
''',
)

FRONTEND_PACKAGE = GeneratedFile(
    path="frontend/package.json",
    content='''{
  "name": "leave-management-web",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build"
  },
  "dependencies": {
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-router-dom": "6.30.6"
  },
  "devDependencies": {
    "@types/react": "19.2.18",
    "@types/react-dom": "19.2.4",
    "@vitejs/plugin-react": "6.1.0",
    "typescript": "7.0.2",
    "vite": "8.1.0"
  }
}
''',
)

FRONTEND_DOCKERFILE = GeneratedFile(
    path="frontend/Dockerfile",
    content='''FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --ignore-scripts
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
''',
)

STACK_CONTRACT_TEST = GeneratedFile(
    path="tests/test_enterprise_contract.py",
    content='''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_enterprise_stack_and_backend_authorization_are_present() -> None:
    program = read("backend/LeaveManagement.Api/Program.cs")
    project = read("backend/LeaveManagement.Api/LeaveManagement.Api.csproj")
    db = read("backend/LeaveManagement.Api/Infrastructure/AppDbContext.cs")
    package = read("frontend/package.json")
    backend_dockerfile = read("backend/LeaveManagement.Api/Dockerfile")
    assert "net10.0" in project
    assert "Microsoft.AspNetCore.Authentication.JwtBearer" in project
    assert "Npgsql.EntityFrameworkCore.PostgreSQL" in project
    assert '"react": "19.2.8"' in package
    assert '"typescript": "7.0.2"' in package
    assert "mcr.microsoft.com/dotnet/sdk:10.0" in backend_dockerfile
    assert 'RequireAuthorization("EmployeeOnly")' in program
    assert 'RequireAuthorization("ManagerOnly")' in program
    assert 'RequireAuthorization("HrOnly")' in program
    assert "UseNpgsql" in program
    assert "leave_requests" in db


def test_critical_business_rules_are_backend_enforced() -> None:
    domain = read("backend/LeaveManagement.Api/Domain/LeaveRequest.cs")
    service = read("backend/LeaveManagement.Api/Application/LeaveService.cs")
    for code in (
        "LEAVE_INVALID_DATE_RANGE",
        "LEAVE_NOT_PENDING",
        "LEAVE_SELF_APPROVAL_FORBIDDEN",
        "LEAVE_APPROVED_IMMUTABLE",
    ):
        assert code in domain
    assert "LEAVE_OVERLAP" in service
    assert "LEAVE_OUTSIDE_MANAGER_SCOPE" in service


def test_react_routes_are_role_aware_and_release_is_containerized() -> None:
    app = read("frontend/src/App.tsx")
    compose = read("docker-compose.yml")
    frontend_dockerfile = read("frontend/Dockerfile")
    assert 'path="/leaves"' in app
    assert 'path="/approvals"' in app
    assert 'path="/reports"' in app
    assert "RoleRoute" in app
    assert "postgres:16-alpine" in compose
    assert "node:22-alpine" in frontend_dockerfile
    assert "nginx:1.29-alpine" in frontend_dockerfile
''',
)


def current_stack_files() -> tuple[GeneratedFile, ...]:
    return (
        API_PROJECT,
        TEST_PROJECT,
        BACKEND_DOCKERFILE,
        FRONTEND_PACKAGE,
        FRONTEND_DOCKERFILE,
        STACK_CONTRACT_TEST,
    )
