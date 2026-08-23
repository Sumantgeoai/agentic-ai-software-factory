from __future__ import annotations

from .contracts import GeneratedFile

MANAGER_SCOPE_DOMAIN = GeneratedFile(
    path="backend/LeaveManagement.Api/Domain/ManagerScope.cs",
    content='''namespace LeaveManagement.Api.Domain;

public sealed class AuthorizationRuleException(string code, string message) : Exception(message)
{
    public string Code { get; } = code;
}

public static class ManagerScope
{
    public static void EnsureCanManage(Guid employeeId, IReadOnlyCollection<Guid> teamEmployeeIds)
    {
        if (!teamEmployeeIds.Contains(employeeId))
            throw new AuthorizationRuleException(
                "LEAVE_OUTSIDE_MANAGER_SCOPE",
                "The leave request is outside the manager's team scope."
            );
    }
}
''',
)

LEAVE_SERVICE = GeneratedFile(
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
            .Select(x => new LeaveView(
                x.Id,
                x.EmployeeId,
                x.StartDate,
                x.EndDate,
                x.Reason,
                x.Status.ToString(),
                x.CreatedAt
            ))
            .ToListAsync(cancellationToken);

    public Task<List<LeaveView>> GetTeamQueueAsync(
        IReadOnlyCollection<Guid> teamEmployeeIds,
        CancellationToken cancellationToken
    ) => db.LeaveRequests
        .Where(x => teamEmployeeIds.Contains(x.EmployeeId) && x.Status == LeaveStatus.Pending)
        .OrderBy(x => x.CreatedAt)
        .Select(x => new LeaveView(
            x.Id,
            x.EmployeeId,
            x.StartDate,
            x.EndDate,
            x.Reason,
            x.Status.ToString(),
            x.CreatedAt
        ))
        .ToListAsync(cancellationToken);

    public async Task<LeaveView> DecideAsync(
        Guid leaveId,
        Guid reviewerEmployeeId,
        IReadOnlyCollection<Guid> teamEmployeeIds,
        bool approve,
        CancellationToken cancellationToken
    )
    {
        var entity = await db.LeaveRequests.SingleOrDefaultAsync(x => x.Id == leaveId, cancellationToken)
            ?? throw new KeyNotFoundException("Leave request not found.");
        ManagerScope.EnsureCanManage(entity.EmployeeId, teamEmployeeIds);
        entity.Decide(reviewerEmployeeId, approve);
        await db.SaveChangesAsync(cancellationToken);
        return ToView(entity);
    }

    public Task<List<LeaveView>> GetAllAsync(CancellationToken cancellationToken) =>
        db.LeaveRequests
            .OrderByDescending(x => x.CreatedAt)
            .Select(x => new LeaveView(
                x.Id,
                x.EmployeeId,
                x.StartDate,
                x.EndDate,
                x.Reason,
                x.Status.ToString(),
                x.CreatedAt
            ))
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
)

PROGRAM = GeneratedFile(
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
    Results.Ok(await service.GetTeamQueueAsync(RequiredTeamEmployeeIds(user), ct))
).RequireAuthorization("ManagerOnly");

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
            RequiredTeamEmployeeIds(user),
            decision.Approve,
            ct
        ));
    }
    catch (AuthorizationRuleException ex)
    {
        return Results.Json(
            new { code = ex.Code, message = ex.Message },
            statusCode: StatusCodes.Status403Forbidden
        );
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

static Guid[] RequiredTeamEmployeeIds(ClaimsPrincipal user) =>
    user.FindAll("team_employee_id")
        .Select(x => Guid.TryParse(x.Value, out var id) ? id : Guid.Empty)
        .Where(x => x != Guid.Empty)
        .Distinct()
        .ToArray();
''',
)

MANAGER_SCOPE_TESTS = GeneratedFile(
    path="backend/LeaveManagement.Tests/ManagerScopeTests.cs",
    content='''using LeaveManagement.Api.Domain;

namespace LeaveManagement.Tests;

public sealed class ManagerScopeTests
{
    [Fact]
    public void Allows_employee_inside_manager_team_scope()
    {
        var employeeId = Guid.NewGuid();
        ManagerScope.EnsureCanManage(employeeId, new[] { employeeId });
    }

    [Fact]
    public void Rejects_employee_outside_manager_team_scope()
    {
        var employeeId = Guid.NewGuid();
        var ex = Assert.Throws<AuthorizationRuleException>(() =>
            ManagerScope.EnsureCanManage(employeeId, new[] { Guid.NewGuid() }));
        Assert.Equal("LEAVE_OUTSIDE_MANAGER_SCOPE", ex.Code);
    }
}
''',
)


def hardened_files() -> tuple[GeneratedFile, ...]:
    return (MANAGER_SCOPE_DOMAIN, LEAVE_SERVICE, PROGRAM, MANAGER_SCOPE_TESTS)
