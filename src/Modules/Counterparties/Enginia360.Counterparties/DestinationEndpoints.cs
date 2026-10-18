using System.Security.Claims;
using Enginia360.Counterparties.Domain;
using Enginia360.Counterparties.Infrastructure;
using Enginia360.Counterparties.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
namespace Enginia360.Counterparties;

internal static class DestinationEndpoints
{
    internal static async Task<IDbContextTransaction> Begin(CounterpartiesDbContext db, CounterpartyAccess grant, Guid company, CancellationToken ct)
    {
        var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {grant.TenantId.ToString()}, true), set_config('app.legal_entity_id', {company.ToString()}, true)", ct);
        return tx;
    }
    internal static async Task<IResult> Create(Guid id, DestinationRequest request, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct)
    {
        var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", request.LegalEntityId, "counterparties.destination.write", ct);
        if (grant is null) return Results.StatusCode(403);
        var address = request.Address?.Trim();
        if (string.IsNullOrEmpty(address) || address.Length > 500) return Results.BadRequest();
        await using var tx = await Begin(db, grant, request.LegalEntityId, ct);
        if (!await db.Counterparties.AnyAsync(x => x.Id == id, ct)) return Results.NotFound();
        var destination = new Destination { Id = Guid.NewGuid(), TenantId = grant.TenantId, CounterpartyId = id, OwnerLegalEntityId = request.LegalEntityId, Address = address };
        db.Destinations.Add(destination);
        await db.SaveChangesAsync(ct);
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/counterparties/destinations/{destination.Id}?legalEntityId={request.LegalEntityId}", ToContract(destination));
    }
    internal static async Task<IResult> List(Guid id, Guid legalEntityId, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct)
    {
        var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", legalEntityId, "counterparties.read", ct);
        if (grant is null) return Results.NotFound();
        await using var tx = await Begin(db, grant, legalEntityId, ct);
        if (!await db.Counterparties.AnyAsync(x => x.Id == id, ct)) return Results.NotFound();
        var rows = await db.Destinations.AsNoTracking().Where(x => x.CounterpartyId == id && (x.OwnerLegalEntityId == legalEntityId || x.Published)).OrderBy(x => x.Id).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return Results.Ok(rows.Select(ToContract));
    }
    internal static async Task<IResult> Get(Guid id, Guid legalEntityId, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct)
    {
        var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", legalEntityId, "counterparties.read", ct);
        if (grant is null) return Results.NotFound();
        await using var tx = await Begin(db, grant, legalEntityId, ct);
        var row = await db.Destinations.AsNoTracking().SingleOrDefaultAsync(x => x.Id == id && (x.OwnerLegalEntityId == legalEntityId || x.Published), ct);
        await tx.CommitAsync(ct);
        return row is null ? Results.NotFound() : Results.Ok(ToContract(row));
    }
    internal static async Task<IResult> Publish(Guid id, CompanyRequest request, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct)
    {
        var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", request.LegalEntityId, "counterparties.destination.publish", ct);
        if (grant is null) return Results.StatusCode(403);
        await using var tx = await Begin(db, grant, request.LegalEntityId, ct);
        var row = await db.Destinations.SingleOrDefaultAsync(x => x.Id == id && x.OwnerLegalEntityId == request.LegalEntityId, ct);
        if (row is null) return Results.NotFound();
        row.Published = true;
        await db.SaveChangesAsync(ct);
        await tx.CommitAsync(ct);
        return Results.Ok(ToContract(row));
    }
    internal static DestinationContract ToContract(Destination x) => new(x.Id, x.CounterpartyId, x.OwnerLegalEntityId, x.Address, x.Published);
}

