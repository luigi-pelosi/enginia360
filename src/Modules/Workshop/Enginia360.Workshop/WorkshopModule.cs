using System.Security.Claims;
using Enginia360.Catalog.Contracts;
using Enginia360.Counterparties.Contracts;
using Enginia360.Vehicles.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Workshop;

public static class WorkshopModule
{
    public static IServiceCollection AddWorkshop(this IServiceCollection services, string connection)
    {
        services.AddDbContext<WorkshopDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<IWorkshopReservationLines, WorkshopReservationLines>();
        services.AddScoped<IWorkshopInstallations, WorkshopInstallations>();
        services.AddScoped<IWorkshopAdministrativeOutbox, WorkshopAdministrativeOutbox>();
        services.AddScoped<IWorkshopBillingSources, WorkshopBillingSources>();
        return services;
    }
    public static WebApplication MapWorkshop(this WebApplication app, bool inventoryEnabled = false, bool externalAdministrationEnabled = false)
    {
        var routes = app.MapGroup("/api/v1/workshop").RequireAuthorization().AddEndpointFilter<TechnicalAuditFilter>();
        routes.MapGet("/contexts", async (ClaimsPrincipal user, IWorkshopAccess access, CancellationToken ct) =>
            Results.Ok(await access.ListContexts(Subject(user), ct)));
        routes.MapGet("/document-types", async (Guid legalEntityId, Guid siteId, ClaimsPrincipal user,
            IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct) =>
        {
            var grant = await access.Authorize(Subject(user), legalEntityId, siteId, "workshop.orders.create", true, ct);
            if (grant is null) return Results.StatusCode(403);
            await using var tx = await db.Database.BeginTransactionAsync(ct);
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {grant.TenantId.ToString()}, true)", ct);
            var types = await db.Configurations.AsNoTracking().Where(x => x.TenantId == grant.TenantId && x.LegalEntityId == legalEntityId)
                .Where(x => !db.Configurations.Any(newer => newer.TenantId == x.TenantId && newer.LegalEntityId == x.LegalEntityId && newer.Id == x.Id && newer.Version > x.Version))
                .OrderBy(x => x.Id).Select(x => new DocumentTypeContract(x.Id, x.Name, x.Version, x.DirectCreationEnabled)).ToListAsync(ct);
            await tx.CommitAsync(ct);
            return Results.Ok(types);
        });
        routes.MapGet("/vehicles", async (Guid legalEntityId, Guid siteId, ClaimsPrincipal user,
            IWorkshopAccess access, IWorkshopVehicles vehicles, CancellationToken ct) =>
        {
            var grant = await access.Authorize(Subject(user), legalEntityId, siteId, "workshop.orders.create", true, ct);
            return grant is null ? Results.StatusCode(403) : Results.Ok(await vehicles.List(grant.TenantId, ct));
        });
        routes.MapPost("/orders", Create);
        routes.MapGet("/catalog", async (Guid legalEntityId, Guid siteId, ClaimsPrincipal user,
            IWorkshopAccess access, IWorkshopCatalog catalog, CancellationToken ct) =>
        {
            var grant = await access.Authorize(Subject(user), legalEntityId, siteId, "workshop.orders.create", true, ct);
            return grant is null ? Results.StatusCode(403) : Results.Ok(await catalog.List(grant.TenantId, ct));
        });
        routes.MapGet("/orders/{id:guid}", Get);
        CommercialEndpoints.Map(routes);
        if (inventoryEnabled) InstallationEndpoints.Map(routes);
        // The carcass requirement of technical closure is evaluated with Inventory receipts.
        if (inventoryEnabled) AdministrativeEndpoints.MapClosure(routes);
        if (inventoryEnabled && externalAdministrationEnabled) AdministrativeEndpoints.MapExternal(routes);
        return app;
    }
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";

    private static async Task<IResult> Create(CreateOrderRequest request, ClaimsPrincipal user,
        IWorkshopAccess access, IWorkshopVehicles vehicles, IWorkshopCounterparties counterparties,
        WorkshopDbContext db, CancellationToken ct)
    {
        if (request.Id == Guid.Empty || request.LegalEntityId == Guid.Empty || request.SiteId == Guid.Empty
            || request.DocumentTypeId == Guid.Empty || request.PayerId == Guid.Empty || request.VehicleId == Guid.Empty
            || request.ConfigurationVersion <= 0) return Results.BadRequest();
        var subject = Subject(user);
        var grant = await access.Authorize(subject, request.LegalEntityId, request.SiteId, "workshop.orders.create", true, ct);
        if (grant is null) return Results.StatusCode(403);
        var vehicle = await vehicles.Find(grant.TenantId, request.VehicleId, ct);
        if (vehicle is null || !await counterparties.CanUsePayer(subject, grant.TenantId, request.LegalEntityId, request.PayerId, ct))
            return Results.NotFound();
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {grant.TenantId.ToString()}, true)", ct);
        var configuration = await db.Configurations.AsNoTracking().SingleOrDefaultAsync(x =>
            x.TenantId == grant.TenantId && x.LegalEntityId == request.LegalEntityId &&
            x.Id == request.DocumentTypeId && x.Version == request.ConfigurationVersion
            && !db.Configurations.Any(newer => newer.TenantId == x.TenantId && newer.LegalEntityId == x.LegalEntityId
                && newer.Id == x.Id && newer.Version > x.Version), ct);
        if (configuration is null || !configuration.DirectCreationEnabled) return Results.Conflict();
        var existing = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (existing is not null)
        {
            var same = existing.LegalEntityId == request.LegalEntityId && existing.SiteId == request.SiteId
                && existing.DocumentTypeId == request.DocumentTypeId && existing.ConfigurationVersion == request.ConfigurationVersion
                && existing.PayerId == request.PayerId && existing.VehicleId == request.VehicleId;
            return same ? Results.Ok(existing.ToContract()) : Results.Conflict();
        }
        var order = new WorkOrder
        {
            Id = request.Id, TenantId = grant.TenantId, LegalEntityId = request.LegalEntityId,
            SiteId = request.SiteId, DocumentTypeId = request.DocumentTypeId,
            ConfigurationVersion = request.ConfigurationVersion, PayerId = request.PayerId,
            VehicleId = vehicle.Id, VehicleHolderId = vehicle.HolderId, CreatedByMembershipId = grant.MembershipId,
        };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.orders ("Id", "TenantId", "LegalEntityId", "SiteId", "DocumentTypeId",
                "ConfigurationVersion", "PayerId", "VehicleId", "VehicleHolderId", "CreatedByMembershipId")
            VALUES ({order.Id}, {order.TenantId}, {order.LegalEntityId}, {order.SiteId}, {order.DocumentTypeId},
                {order.ConfigurationVersion}, {order.PayerId}, {order.VehicleId}, {order.VehicleHolderId}, {order.CreatedByMembershipId})
            ON CONFLICT ("Id") DO NOTHING
            """, ct);
        if (inserted == 0)
        {
            var concurrent = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
            return concurrent is not null && concurrent.ToContract() == order.ToContract()
                ? Results.Ok(concurrent.ToContract()) : Results.Conflict();
        }
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/workshop/orders/{order.Id}", order.ToContract());
    }

    private static async Task<IResult> Get(Guid id, ClaimsPrincipal user, IWorkshopAccess access,
        WorkshopDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        WorkOrder? row;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", ct);
            row = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
            await tx.CommitAsync(ct);
        }
        if (row is null || await access.Authorize(subject, row.LegalEntityId, row.SiteId, "workshop.orders.read", false, ct) is null)
            return Results.NotFound();
        return Results.Ok(row.ToContract());
    }
}
