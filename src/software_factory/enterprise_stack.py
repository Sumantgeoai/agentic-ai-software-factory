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


def current_stack_files() -> tuple[GeneratedFile, ...]:
    return (
        API_PROJECT,
        TEST_PROJECT,
        BACKEND_DOCKERFILE,
        FRONTEND_PACKAGE,
        FRONTEND_DOCKERFILE,
    )
