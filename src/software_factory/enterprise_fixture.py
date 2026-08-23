from __future__ import annotations

from .contracts import (
    AgentRole,
    ArchitectureSpec,
    ArtifactSet,
    CodeBundle,
    GeneratedFile,
    RequirementSpec,
    TargetProfile,
    TaskPlan,
    WorkItem,
)
from .specification import (
    ApplicationSpec,
    BusinessRuleSpec,
    EntityFieldSpec,
    EntitySpec,
    PageSpec,
    PermissionSpec,
    RoleSpec,
    WorkflowSpec,
    WorkflowStepSpec,
)


def enterprise_requirements() -> RequirementSpec:
    return RequirementSpec(
        product_name="Leave Management",
        actors=["employee", "manager", "hr"],
        functional_requirements=[
            "Employees can create and view their own leave requests",
            "Managers can review team leave requests and approve or reject pending requests",
            "HR can view organization-wide leave reporting",
            "Navigation and pages are visible only to the appropriate application roles",
        ],
        non_functional_requirements=[
            "ASP.NET Core enforces authorization and business rules server-side",
            "PostgreSQL stores durable leave request state",
            "React and TypeScript provide a multi-page role-aware user experience",
            "Critical business rules have deterministic automated tests",
        ],
        constraints=[
            "Frontend route visibility is not an authorization boundary",
            "Generated execution remains inside the governed workspace runtime",
        ],
        acceptance_criteria=[
            "Employee, Manager and HR receive distinct application routes",
            "Only pending requests can be approved or rejected",
            "A manager cannot approve their own leave request",
            "Invalid date ranges and overlapping approved leave are rejected",
            "The release contains ASP.NET Core, React, PostgreSQL migration and Docker Compose assets",
        ],
    )


def enterprise_architecture() -> ArchitectureSpec:
    return ArchitectureSpec(
        summary=(
            "Modular ASP.NET Core Web API with backend-enforced authorization and domain rules, "
            "a React/TypeScript SPA, and PostgreSQL persistence behind EF Core."
        ),
        backend="ASP.NET Core Web API / .NET 8",
        frontend="React 18 + TypeScript + React Router + Vite",
        database="PostgreSQL with EF Core/Npgsql and explicit migration",
        authentication="OIDC/JWT bearer authentication with backend role policies",
        services=["leave-api", "leave-web", "postgres"],
        security_constraints=[
            "Backend authorization is authoritative; frontend guards are UX only",
            "No generated secret is embedded in source or compose files",
            "Manager team scope is derived from authenticated claims",
            "All generated files remain inside the governed workspace",
        ],
        decisions=[
            "Use domain methods for stable business-rule enforcement and error codes",
            "Use PostgreSQL constraints for durable relational integrity where appropriate",
            "Keep identity-provider configuration external to the generated release",
        ],
    )


def enterprise_application_spec() -> ApplicationSpec:
    return ApplicationSpec(
        target_profile=TargetProfile.ENTERPRISE_DOTNET_REACT,
        roles=[
            RoleSpec(name="employee", description="Creates and tracks own leave requests"),
            RoleSpec(name="manager", description="Reviews leave requests for managed employees"),
            RoleSpec(name="hr", description="Views organization-wide leave reporting"),
        ],
        permissions=[
            PermissionSpec(
                role="employee",
                resource="leave-request",
                actions=["create", "read", "edit"],
                scope="own",
            ),
            PermissionSpec(
                role="manager",
                resource="leave-request",
                actions=["read", "approve", "reject"],
                scope="team",
            ),
            PermissionSpec(
                role="hr",
                resource="leave-report",
                actions=["read", "export"],
                scope="all",
            ),
        ],
        pages=[
            PageSpec(
                id="dashboard",
                route="/",
                title="Dashboard",
                allowed_roles=["employee", "manager", "hr"],
            ),
            PageSpec(
                id="my-leaves",
                route="/leaves",
                title="My Leaves",
                allowed_roles=["employee"],
                capabilities=["read-own-leave"],
            ),
            PageSpec(
                id="apply-leave",
                route="/leaves/new",
                title="Apply Leave",
                allowed_roles=["employee"],
                capabilities=["create-leave"],
            ),
            PageSpec(
                id="approval-queue",
                route="/approvals",
                title="Approval Queue",
                allowed_roles=["manager"],
                capabilities=["approve-team-leave", "reject-team-leave"],
            ),
            PageSpec(
                id="reports",
                route="/reports",
                title="Reports",
                allowed_roles=["hr"],
                capabilities=["read-all-leave"],
            ),
        ],
        entities=[
            EntitySpec(
                name="LeaveRequest",
                fields=[
                    EntityFieldSpec(name="Id", data_type="uuid"),
                    EntityFieldSpec(name="EmployeeId", data_type="uuid"),
                    EntityFieldSpec(name="StartDate", data_type="date"),
                    EntityFieldSpec(name="EndDate", data_type="date"),
                    EntityFieldSpec(name="Reason", data_type="string"),
                    EntityFieldSpec(name="Status", data_type="enum"),
                    EntityFieldSpec(name="CreatedAt", data_type="datetime"),
                ],
            )
        ],
        business_rules=[
            BusinessRuleSpec(
                id="BR-LEAVE-DATE-RANGE",
                name="Valid leave date range",
                description="End date cannot precede start date.",
                entity="LeaveRequest",
                trigger="create or edit leave request",
                condition="EndDate >= StartDate",
                outcome="accept date range",
                allowed_roles=["employee"],
                error_code="LEAVE_INVALID_DATE_RANGE",
            ),
            BusinessRuleSpec(
                id="BR-LEAVE-PENDING",
                name="Only pending leave can be decided",
                description="Approved or rejected requests cannot be decided again.",
                entity="LeaveRequest",
                trigger="approve or reject leave request",
                condition="Status == Pending",
                outcome="transition to Approved or Rejected",
                allowed_roles=["manager"],
                error_code="LEAVE_NOT_PENDING",
            ),
            BusinessRuleSpec(
                id="BR-LEAVE-SELF-APPROVAL",
                name="No self approval",
                description="A manager cannot approve or reject their own leave request.",
                entity="LeaveRequest",
                trigger="approve or reject leave request",
                condition="ReviewerEmployeeId != EmployeeId",
                outcome="allow decision",
                allowed_roles=["manager"],
                error_code="LEAVE_SELF_APPROVAL_FORBIDDEN",
            ),
            BusinessRuleSpec(
                id="BR-LEAVE-IMMUTABLE",
                name="Approved leave is immutable",
                description="Approved leave cannot be edited through the employee workflow.",
                entity="LeaveRequest",
                trigger="edit leave request",
                condition="Status != Approved",
                outcome="allow edit",
                allowed_roles=["employee"],
                error_code="LEAVE_APPROVED_IMMUTABLE",
            ),
            BusinessRuleSpec(
                id="BR-LEAVE-OVERLAP",
                name="No overlapping approved leave",
                description="A new request cannot overlap existing approved leave for the employee.",
                entity="LeaveRequest",
                trigger="create leave request",
                condition="No approved request overlaps requested date range",
                outcome="allow create",
                allowed_roles=["employee"],
                error_code="LEAVE_OVERLAP",
            ),
        ],
        workflows=[
            WorkflowSpec(
                name="Leave submission",
                steps=[
                    WorkflowStepSpec(
                        id="submit",
                        actor="employee",
                        action="submit valid leave request",
                        result="pending leave request",
                    )
                ],
            ),
            WorkflowSpec(
                name="Leave approval",
                steps=[
                    WorkflowStepSpec(
                        id="review",
                        actor="manager",
                        action="review team pending request",
                        result="decision candidate",
                    ),
                    WorkflowStepSpec(
                        id="decide",
                        actor="manager",
                        action="approve or reject request",
                        result="approved or rejected leave request",
                    ),
                ],
            ),
            WorkflowSpec(
                name="Leave reporting",
                steps=[
                    WorkflowStepSpec(
                        id="report",
                        actor="hr",
                        action="view organization leave report",
                        result="organization-wide leave data",
                    )
                ],
            ),
        ],
    )


def enterprise_task_plan() -> TaskPlan:
    return TaskPlan(
        items=[
            WorkItem(
                id="DB-1",
                title="Create PostgreSQL EF Core persistence and migration",
                owner=AgentRole.DATABASE,
                acceptance_criteria=["LeaveRequest schema and migration are explicit and durable"],
            ),
            WorkItem(
                id="API-1",
                title="Implement ASP.NET Core domain, authorization and API endpoints",
                owner=AgentRole.BACKEND,
                depends_on=["DB-1"],
                acceptance_criteria=[
                    "Employee, Manager and HR policies are enforced server-side",
                    "Critical leave business rules return stable error codes",
                ],
            ),
            WorkItem(
                id="UI-1",
                title="Implement React role-aware multi-page application",
                owner=AgentRole.FRONTEND,
                depends_on=["API-1"],
                acceptance_criteria=[
                    "Role-specific routes and navigation exist for Employee, Manager and HR"
                ],
            ),
            WorkItem(
                id="QA-1",
                title="Add domain-rule and generated-contract tests",
                owner=AgentRole.QA,
                depends_on=["API-1", "UI-1"],
                acceptance_criteria=["Critical business rules and target-stack artifacts are tested"],
            ),
            WorkItem(
                id="OPS-1",
                title="Package API, SPA and PostgreSQL with Docker Compose",
                owner=AgentRole.DEVOPS,
                depends_on=["QA-1"],
                acceptance_criteria=["Release has container build files and externalized configuration"],
            ),
        ]
    )


def enterprise_artifacts(system: str) -> ArtifactSet:
    role = system.lower()
    if "database specialist" in role:
        return ArtifactSet(files=_database_files())
    if "backend specialist" in role:
        return ArtifactSet(files=_backend_files())
    if "frontend specialist" in role:
        return ArtifactSet(files=_frontend_files())
    if "qa specialist" in role:
        return ArtifactSet(files=_qa_files())
    if "devops specialist" in role:
        return ArtifactSet(files=_devops_files())
    raise ValueError("Enterprise fixture could not identify specialist role")


def enterprise_bundle() -> CodeBundle:
    sets = [
        enterprise_artifacts("database specialist"),
        enterprise_artifacts("backend specialist"),
        enterprise_artifacts("frontend specialist"),
        enterprise_artifacts("qa specialist"),
        enterprise_artifacts("devops specialist"),
    ]
    return CodeBundle(files=[file for artifact in sets for file in artifact.files])


def _database_files() -> list[GeneratedFile]:
    return [
        GeneratedFile(
            path="backend/LeaveManagement.Api/Infrastructure/AppDbContext.cs",
            content='''using LeaveManagement.Api.Domain;
using Microsoft.EntityFrameworkCore;

namespace LeaveManagement.Api.Infrastructure;

public sealed class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<LeaveRequest> LeaveRequests => Set<LeaveRequest>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        var leave = modelBuilder.Entity<LeaveRequest>();
        leave.ToTable("leave_requests");
        leave.HasKey(x => x.Id);
        leave.Property(x => x.Reason).HasMaxLength(500).IsRequired();
        leave.Property(x => x.Status).HasConversion<string>().HasMaxLength(20).IsRequired();
        leave.HasIndex(x => new { x.EmployeeId, x.StartDate, x.EndDate });
        leave.ToTable(t => t.HasCheckConstraint("ck_leave_date_range", "\\\"EndDate\\\" >= \\\"StartDate\\\""));
    }
}
''',
        ),
        GeneratedFile(
            path="backend/LeaveManagement.Api/Infrastructure/Migrations/202608240001_Initial.cs",
            content='''using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace LeaveManagement.Api.Infrastructure.Migrations;

public partial class Initial : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.CreateTable(
            name: "leave_requests",
            columns: table => new
            {
                Id = table.Column<Guid>(type: "uuid", nullable: false),
                EmployeeId = table.Column<Guid>(type: "uuid", nullable: false),
                StartDate = table.Column<DateOnly>(type: "date", nullable: false),
                EndDate = table.Column<DateOnly>(type: "date", nullable: false),
                Reason = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: false),
                Status = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                CreatedAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
            },
            constraints: table =>
            {
                table.PrimaryKey("PK_leave_requests", x => x.Id);
                table.CheckConstraint("ck_leave_date_range", "\\\"EndDate\\\" >= \\\"StartDate\\\"");
            });

        migrationBuilder.CreateIndex(
            name: "IX_leave_requests_EmployeeId_StartDate_EndDate",
            table: "leave_requests",
            columns: new[] { "EmployeeId", "StartDate", "EndDate" });
    }

    protected override void Down(MigrationBuilder migrationBuilder) =>
        migrationBuilder.DropTable(name: "leave_requests");
}
''',
        ),
    ]


def _backend_files() -> list[GeneratedFile]:
    return [
        GeneratedFile(
            path="backend/LeaveManagement.Api/LeaveManagement.Api.csproj",
            content='''<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="8.0.8">
      <PrivateAssets>all</PrivateAssets>
      <IncludeAssets>runtime; build; native; contentfiles; analyzers; buildtransitive</IncludeAssets>
    </PackageReference>
    <PackageReference Include="Npgsql.EntityFrameworkCore.PostgreSQL" Version="8.0.4" />
  </ItemGroup>
</Project>
''',
        ),
        GeneratedFile(
            path="backend/LeaveManagement.Api/Domain/LeaveRequest.cs",
            content='''namespace LeaveManagement.Api.Domain;

public enum LeaveStatus
{
    Pending,
    Approved,
    Rejected
}

public sealed class DomainRuleException(string code, string message) : Exception(message)
{
    public string Code { get; } = code;
}

public sealed class LeaveRequest
{
    private LeaveRequest() { }

    private LeaveRequest(Guid employeeId, DateOnly startDate, DateOnly endDate, string reason)
    {
        Id = Guid.NewGuid();
        EmployeeId = employeeId;
        SetDates(startDate, endDate);
        Reason = string.IsNullOrWhiteSpace(reason)
            ? throw new DomainRuleException("LEAVE_REASON_REQUIRED", "Reason is required.")
            : reason.Trim();
        Status = LeaveStatus.Pending;
        CreatedAt = DateTimeOffset.UtcNow;
    }

    public Guid Id { get; private set; }
    public Guid EmployeeId { get; private set; }
    public DateOnly StartDate { get; private set; }
    public DateOnly EndDate { get; private set; }
    public string Reason { get; private set; } = string.Empty;
    public LeaveStatus Status { get; private set; }
    public DateTimeOffset CreatedAt { get; private set; }

    public static LeaveRequest Create(Guid employeeId, DateOnly startDate, DateOnly endDate, string reason) =>
        new(employeeId, startDate, endDate, reason);

    public void EditDates(DateOnly startDate, DateOnly endDate)
    {
        if (Status == LeaveStatus.Approved)
            throw new DomainRuleException("LEAVE_APPROVED_IMMUTABLE", "Approved leave cannot be edited.");
        SetDates(startDate, endDate);
    }

    public void Decide(Guid reviewerEmployeeId, bool approve)
    {
        if (Status != LeaveStatus.Pending)
            throw new DomainRuleException("LEAVE_NOT_PENDING", "Only pending leave can be decided.");
        if (reviewerEmployeeId == EmployeeId)
            throw new DomainRuleException(
                "LEAVE_SELF_APPROVAL_FORBIDDEN",
                "A manager cannot decide their own leave request."
            );
        Status = approve ? LeaveStatus.Approved : LeaveStatus.Rejected;
    }

    private void SetDates(DateOnly startDate, DateOnly endDate)
    {
        if (endDate < startDate)
            throw new DomainRuleException("LEAVE_INVALID_DATE_RANGE", "End date must be on or after start date.");
        StartDate = startDate;
        EndDate = endDate;
    }
}
''',
        ),
        GeneratedFile(
            path="backend/LeaveManagement.Api/Contracts/LeaveContracts.cs",
            content='''namespace LeaveManagement.Api.Contracts;

public sealed record CreateLeaveRequest(DateOnly StartDate, DateOnly EndDate, string Reason);
public sealed record LeaveDecision(bool Approve);
public sealed record LeaveView(
    Guid Id,
    Guid EmployeeId,
    DateOnly StartDate,
    DateOnly EndDate,
    string Reason,
    string Status,
    DateTimeOffset CreatedAt
);
''',
        ),
        GeneratedFile(
            path="backend/LeaveManagement.Api/Application/LeaveService.cs",
            content='''using LeaveManagement.Api.Contracts;
using LeaveManagement.Api.Domain;
using LeaveManagement.Api.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace LeaveManagement.Api.Application;

public sealed class LeaveService(AppDbContext db)
{
    public async Task<LeaveView> CreateAsync(
        Guid employeeId,
        CreateLeaveRequest request,
        CancellationToken cancellationToken
    )
    {
        var entity = LeaveRequest.Create(employeeId, request.StartDate, request.EndDate, request.Reason);
        var overlapsApproved = await db.LeaveRequests.AnyAsync(
            x => x.EmployeeId == employeeId
                && x.Status == LeaveStatus.Approved
                && x.StartDate <= request.EndDate
                && x.EndDate >= request.StartDate,
            cancellationToken
        );
        if (overlapsApproved)
            throw new DomainRuleException("LEAVE_OVERLAP", "Requested dates overlap approved leave.");

        db.LeaveRequests.Add(entity);
        await db.SaveChangesAsync(cancellationToken);
        return ToView(entity);
    }

    public Task<List<LeaveView>> GetOwnAsync(Guid employeeId, CancellationToken cancellationToken) =>
        db.LeaveRequests
            .Where(x => x.EmployeeId == employeeId)
            .OrderByDescending(x => x.CreatedAt)
            .Select(x => ToView(x))
            .ToListAsync(cancellationToken);

    public Task<List<LeaveView>> GetTeamQueueAsync(
        IReadOnlyCollection<Guid> teamEmployeeIds,
        CancellationToken cancellationToken
    ) => db.LeaveRequests
        .Where(x => teamEmployeeIds.Contains(x.EmployeeId) && x.Status == LeaveStatus.Pending)
        .OrderBy(x => x.CreatedAt)
        .Select(x => ToView(x))
        .ToListAsync(cancellationToken);

    public async Task<LeaveView> DecideAsync(
        Guid leaveId,
        Guid reviewerEmployeeId,
        bool approve,
        CancellationToken cancellationToken
    )
    {
        var entity = await db.LeaveRequests.SingleOrDefaultAsync(x => x.Id == leaveId, cancellationToken)
            ?? throw new KeyNotFoundException("Leave request not found.");
        entity.Decide(reviewerEmployeeId, approve);
        await db.SaveChangesAsync(cancellationToken);
        return ToView(entity);
    }

    public Task<List<LeaveView>> GetAllAsync(CancellationToken cancellationToken) =>
        db.LeaveRequests
            .OrderByDescending(x => x.CreatedAt)
            .Select(x => ToView(x))
            .ToListAsync(cancellationToken);

    private static LeaveView ToView(LeaveRequest item) => new(
        item.Id,
        item.EmployeeId,
        item.StartDate,
        item.EndDate,
        item.Reason,
        item.Status.ToString(),
        item.CreatedAt
    );
}
''',
        ),
        GeneratedFile(
            path="backend/LeaveManagement.Api/Program.cs",
            content='''using System.Security.Claims;
using LeaveManagement.Api.Application;
using LeaveManagement.Api.Contracts;
using LeaveManagement.Api.Domain;
using LeaveManagement.Api.Infrastructure;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("Postgres")));
builder.Services.AddScoped<LeaveService>();
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(options =>
{
    options.Authority = builder.Configuration["Authentication:Authority"];
    options.Audience = builder.Configuration["Authentication:Audience"];
});
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("EmployeeOnly", policy => policy.RequireRole("Employee"));
    options.AddPolicy("ManagerOnly", policy => policy.RequireRole("Manager"));
    options.AddPolicy("HrOnly", policy => policy.RequireRole("HR"));
});

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();

app.MapPost("/api/leaves", async (
    ClaimsPrincipal user,
    CreateLeaveRequest request,
    LeaveService service,
    CancellationToken ct) =>
{
    try
    {
        var employeeId = RequiredEmployeeId(user);
        return Results.Created("/api/leaves", await service.CreateAsync(employeeId, request, ct));
    }
    catch (DomainRuleException ex)
    {
        return Results.Conflict(new { code = ex.Code, message = ex.Message });
    }
}).RequireAuthorization("EmployeeOnly");

app.MapGet("/api/leaves/mine", async (
    ClaimsPrincipal user,
    LeaveService service,
    CancellationToken ct) =>
    Results.Ok(await service.GetOwnAsync(RequiredEmployeeId(user), ct))
).RequireAuthorization("EmployeeOnly");

app.MapGet("/api/approvals", async (
    ClaimsPrincipal user,
    LeaveService service,
    CancellationToken ct) =>
{
    var team = user.FindAll("team_employee_id")
        .Select(x => Guid.TryParse(x.Value, out var id) ? id : Guid.Empty)
        .Where(x => x != Guid.Empty)
        .ToArray();
    return Results.Ok(await service.GetTeamQueueAsync(team, ct));
}).RequireAuthorization("ManagerOnly");

app.MapPatch("/api/approvals/{leaveId:guid}", async (
    Guid leaveId,
    ClaimsPrincipal user,
    LeaveDecision decision,
    LeaveService service,
    CancellationToken ct) =>
{
    try
    {
        return Results.Ok(await service.DecideAsync(
            leaveId,
            RequiredEmployeeId(user),
            decision.Approve,
            ct
        ));
    }
    catch (DomainRuleException ex)
    {
        return Results.Conflict(new { code = ex.Code, message = ex.Message });
    }
    catch (KeyNotFoundException)
    {
        return Results.NotFound();
    }
}).RequireAuthorization("ManagerOnly");

app.MapGet("/api/reports/leaves", async (LeaveService service, CancellationToken ct) =>
    Results.Ok(await service.GetAllAsync(ct))
).RequireAuthorization("HrOnly");

app.Run();

static Guid RequiredEmployeeId(ClaimsPrincipal user)
{
    var value = user.FindFirstValue("employee_id") ?? user.FindFirstValue(ClaimTypes.NameIdentifier);
    return Guid.TryParse(value, out var employeeId)
        ? employeeId
        : throw new UnauthorizedAccessException("Authenticated employee identifier is required.");
}
''',
        ),
    ]


def _frontend_files() -> list[GeneratedFile]:
    return [
        GeneratedFile(
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
    "@vitejs/plugin-react": "4.3.4",
    "vite": "5.4.11",
    "typescript": "5.7.2",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "react-router-dom": "6.28.0"
  },
  "devDependencies": {
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1"
  }
}
''',
        ),
        GeneratedFile(
            path="frontend/tsconfig.json",
            content='''{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
''',
        ),
        GeneratedFile(
            path="frontend/vite.config.ts",
            content='''import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
''',
        ),
        GeneratedFile(
            path="frontend/index.html",
            content='''<!doctype html>
<html lang="en">
  <head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>Leave Management</title></head>
  <body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>
''',
        ),
        GeneratedFile(
            path="frontend/src/main.tsx",
            content='''import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { RoleProvider } from "./role";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <RoleProvider><App /></RoleProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
''',
        ),
        GeneratedFile(
            path="frontend/src/role.tsx",
            content='''import { createContext, ReactNode, useContext, useMemo, useState } from "react";

export type Role = "employee" | "manager" | "hr";
type RoleContextValue = { role: Role; setRole: (role: Role) => void };
const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>("employee");
  const value = useMemo(() => ({ role, setRole }), [role]);
  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole() {
  const value = useContext(RoleContext);
  if (!value) throw new Error("RoleProvider is required");
  return value;
}
''',
        ),
        GeneratedFile(
            path="frontend/src/api.ts",
            content='''export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem("access_token");
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return response.json() as Promise<T>;
}
''',
        ),
        GeneratedFile(
            path="frontend/src/pages.tsx",
            content='''import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "./api";

type Leave = { id: string; startDate: string; endDate: string; reason: string; status: string };

export function DashboardPage() { return <section><h2>Dashboard</h2><p>Role-aware leave operations and status.</p></section>; }

export function MyLeavesPage() {
  const [items, setItems] = useState<Leave[]>([]);
  useEffect(() => { apiFetch<Leave[]>("/api/leaves/mine").then(setItems).catch(() => setItems([])); }, []);
  return <section><h2>My Leaves</h2><ul>{items.map(x => <li key={x.id}>{x.startDate} - {x.endDate}: {x.status}</li>)}</ul></section>;
}

export function ApplyLeavePage() {
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await apiFetch("/api/leaves", { method: "POST", body: JSON.stringify({ startDate: data.get("startDate"), endDate: data.get("endDate"), reason: data.get("reason") }) });
    setMessage("Leave request submitted.");
  }
  return <section><h2>Apply Leave</h2><form onSubmit={submit}><input name="startDate" type="date" required /><input name="endDate" type="date" required /><input name="reason" required minLength={3} /><button type="submit">Submit</button></form><p>{message}</p></section>;
}

export function ApprovalQueuePage() { return <section><h2>Approval Queue</h2><p>Manager team-scope decisions are authorized by the API.</p></section>; }
export function ReportsPage() { return <section><h2>Reports</h2><p>HR organization-wide leave reporting.</p></section>; }
export function ForbiddenPage() { return <section><h2>Not authorized</h2></section>; }
''',
        ),
        GeneratedFile(
            path="frontend/src/App.tsx",
            content='''import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { ApplyLeavePage, ApprovalQueuePage, DashboardPage, ForbiddenPage, MyLeavesPage, ReportsPage } from "./pages";
import { Role, useRole } from "./role";

function RoleRoute({ allowed, children }: { allowed: Role[]; children: JSX.Element }) {
  const { role } = useRole();
  return allowed.includes(role) ? children : <Navigate to="/forbidden" replace />;
}

export function App() {
  const { role, setRole } = useRole();
  return <main>
    <header><h1>Leave Management</h1><label>Demo UI role <select value={role} onChange={e => setRole(e.target.value as Role)}><option value="employee">Employee</option><option value="manager">Manager</option><option value="hr">HR</option></select></label></header>
    <nav>
      <NavLink to="/">Dashboard</NavLink>{" "}
      {role === "employee" && <><NavLink to="/leaves">My Leaves</NavLink>{" "}<NavLink to="/leaves/new">Apply Leave</NavLink></>}
      {role === "manager" && <NavLink to="/approvals">Approvals</NavLink>}
      {role === "hr" && <NavLink to="/reports">Reports</NavLink>}
    </nav>
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/leaves" element={<RoleRoute allowed={["employee"]}><MyLeavesPage /></RoleRoute>} />
      <Route path="/leaves/new" element={<RoleRoute allowed={["employee"]}><ApplyLeavePage /></RoleRoute>} />
      <Route path="/approvals" element={<RoleRoute allowed={["manager"]}><ApprovalQueuePage /></RoleRoute>} />
      <Route path="/reports" element={<RoleRoute allowed={["hr"]}><ReportsPage /></RoleRoute>} />
      <Route path="/forbidden" element={<ForbiddenPage />} />
    </Routes>
  </main>;
}
''',
        ),
    ]


def _qa_files() -> list[GeneratedFile]:
    return [
        GeneratedFile(
            path="backend/LeaveManagement.Tests/LeaveManagement.Tests.csproj",
            content='''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
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
        ),
        GeneratedFile(
            path="backend/LeaveManagement.Tests/LeaveRequestTests.cs",
            content='''using LeaveManagement.Api.Domain;

namespace LeaveManagement.Tests;

public sealed class LeaveRequestTests
{
    [Fact]
    public void Rejects_invalid_date_range()
    {
        var ex = Assert.Throws<DomainRuleException>(() => LeaveRequest.Create(
            Guid.NewGuid(), new DateOnly(2026, 8, 10), new DateOnly(2026, 8, 9), "Test"));
        Assert.Equal("LEAVE_INVALID_DATE_RANGE", ex.Code);
    }

    [Fact]
    public void Rejects_self_approval()
    {
        var employeeId = Guid.NewGuid();
        var leave = LeaveRequest.Create(employeeId, new DateOnly(2026, 8, 10), new DateOnly(2026, 8, 12), "Test");
        var ex = Assert.Throws<DomainRuleException>(() => leave.Decide(employeeId, true));
        Assert.Equal("LEAVE_SELF_APPROVAL_FORBIDDEN", ex.Code);
    }

    [Fact]
    public void Rejects_second_decision()
    {
        var leave = LeaveRequest.Create(Guid.NewGuid(), new DateOnly(2026, 8, 10), new DateOnly(2026, 8, 12), "Test");
        leave.Decide(Guid.NewGuid(), true);
        var ex = Assert.Throws<DomainRuleException>(() => leave.Decide(Guid.NewGuid(), false));
        Assert.Equal("LEAVE_NOT_PENDING", ex.Code);
    }
}
''',
        ),
        GeneratedFile(
            path="tests/test_enterprise_contract.py",
            content='''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_enterprise_stack_and_backend_authorization_are_present() -> None:
    program = read("backend/LeaveManagement.Api/Program.cs")
    project = read("backend/LeaveManagement.Api/LeaveManagement.Api.csproj")
    db = read("backend/LeaveManagement.Api/Infrastructure/AppDbContext.cs")
    assert "net8.0" in project
    assert "Npgsql.EntityFrameworkCore.PostgreSQL" in project
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


def test_react_routes_are_role_aware_and_release_is_containerized() -> None:
    app = read("frontend/src/App.tsx")
    compose = read("docker-compose.yml")
    assert 'path="/leaves"' in app
    assert 'path="/approvals"' in app
    assert 'path="/reports"' in app
    assert "RoleRoute" in app
    assert "postgres:16-alpine" in compose
''',
        ),
    ]


def _devops_files() -> list[GeneratedFile]:
    return [
        GeneratedFile(
            path="backend/LeaveManagement.Api/Dockerfile",
            content='''FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish LeaveManagement.Api.csproj -c Release -o /out --no-self-contained

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /out .
USER 10001
ENTRYPOINT ["dotnet", "LeaveManagement.Api.dll"]
''',
        ),
        GeneratedFile(
            path="frontend/Dockerfile",
            content='''FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --ignore-scripts
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
''',
        ),
        GeneratedFile(
            path="frontend/nginx.conf",
            content='''server {
  listen 8080;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;
  location / { try_files $uri $uri/ /index.html; }
  location /api/ { proxy_pass http://api:8080; proxy_set_header Host $host; }
}
''',
        ),
        GeneratedFile(
            path="docker-compose.yml",
            content='''services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: leave_management
      POSTGRES_USER: leave_app
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U leave_app -d leave_management"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - leave_db:/var/lib/postgresql/data

  api:
    build:
      context: ./backend/LeaveManagement.Api
    environment:
      ASPNETCORE_URLS: http://+:8080
      ConnectionStrings__Postgres: Host=db;Port=5432;Database=leave_management;Username=leave_app;Password=${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}
      Authentication__Authority: ${OIDC_AUTHORITY:-https://identity.example.invalid}
      Authentication__Audience: ${OIDC_AUDIENCE:-leave-management-api}
    depends_on:
      db:
        condition: service_healthy

  web:
    build:
      context: ./frontend
    ports:
      - "8088:8080"
    depends_on:
      - api

volumes:
  leave_db:
''',
        ),
        GeneratedFile(
            path="README.md",
            content='''# Leave Management - enterprise-dotnet-react

Generated stack: React + TypeScript, ASP.NET Core Web API, PostgreSQL/EF Core and Docker Compose.

## Security boundary

Frontend role selection and route guards demonstrate navigation behavior only. Production authorization is enforced by ASP.NET Core JWT role policies. Configure the external OIDC authority/audience and issue `employee_id` plus `team_employee_id` claims from the trusted identity/entitlement layer.

## Local integration

Set `POSTGRES_PASSWORD`, `OIDC_AUTHORITY` and `OIDC_AUDIENCE`, then run `docker compose up --build`.

The software-factory runtime currently performs its governed Python structural contract gate for this generated target. The generated release also includes xUnit domain tests and buildable .NET/React projects so a toolchain-capable isolated worker or CI can run `dotnet test` and `npm run build` as the next promotion gate.
''',
        ),
    ]
