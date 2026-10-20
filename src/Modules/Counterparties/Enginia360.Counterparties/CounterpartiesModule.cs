using System.Security.Claims;
using Enginia360.Counterparties.Domain;
using Enginia360.Counterparties.Infrastructure;
using Enginia360.Counterparties.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Counterparties;

public static class CounterpartiesModule
{
    public static IServiceCollection AddCounterparties(this IServiceCollection services, string connection)
    {
        services.AddDbContext<CounterpartiesDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<WorkshopCounterparties>();
        services.AddScoped<IWorkshopCounterparties>(provider => provider.GetRequiredService<WorkshopCounterparties>());
        services.AddScoped<IInvoiceCounterparties>(provider => provider.GetRequiredService<WorkshopCounterparties>());
        return services;
    }
    public static WebApplication MapCounterparties(this WebApplication app)
    {
        var routes = app.MapGroup("/api/v1/counterparties").RequireAuthorization().AddEndpointFilter<TechnicalAuditFilter>();
        routes.MapGet("/companies", async (ClaimsPrincipal user, ICounterpartyAccess access, CancellationToken ct) => Results.Ok(await access.ListCompanies(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", ct)));
        routes.MapGet("", async (Guid legalEntityId, string? search, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct) =>
        {
            var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", legalEntityId, "counterparties.read", ct);
            if (grant is null) return Results.StatusCode(403);
            await using var tx = await db.Database.BeginTransactionAsync(ct);
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {grant.TenantId.ToString()}, true)", ct);
            if (search is { Length: > 200 }) return Results.BadRequest();
            var rows = await db.Counterparties.AsNoTracking().Where(x => search == null || x.LegalName.Contains(search)).OrderBy(x => x.Id).Select(x => new CounterpartyContract(x.Id, x.TenantId, x.LegalName, x.FiscalIdentifier, x.RegisteredOffice)).ToListAsync(ct);
            await tx.CommitAsync(ct);
            return Results.Ok(rows);
        });
        routes.MapGet("/{id:guid}", async (Guid id, Guid legalEntityId, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct) =>
        {
            var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", legalEntityId, "counterparties.read", ct);
            if (grant is null) return Results.NotFound();
            await using var tx = await db.Database.BeginTransactionAsync(ct);
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {grant.TenantId.ToString()}, true)", ct);
            var row = await db.Counterparties.AsNoTracking().Where(x => x.Id == id).Select(x => new CounterpartyContract(x.Id, x.TenantId, x.LegalName, x.FiscalIdentifier, x.RegisteredOffice)).SingleOrDefaultAsync(ct);
            await tx.CommitAsync(ct);
            return row is null ? Results.NotFound() : Results.Ok(row);
        });
        routes.MapPut("/{id:guid}", CommonEndpoints.Update);
        routes.MapPost("/destinations/{id:guid}/publication", DestinationEndpoints.Publish);
        routes.MapPost("/{id:guid}/destinations", DestinationEndpoints.Create);
        routes.MapGet("/{id:guid}/destinations", DestinationEndpoints.List);
        routes.MapGet("/destinations/{id:guid}", DestinationEndpoints.Get);
        return app;
    }
}


