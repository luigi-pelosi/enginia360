using System.Security.Claims;
using Enginia360.Counterparties.Domain;
using Enginia360.Counterparties.Infrastructure;
using Enginia360.Counterparties.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
namespace Enginia360.Counterparties;
internal static class CommonEndpoints
{
    internal static async Task<IResult> Update(Guid id, UpdateCounterpartyRequest request, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct)
    {
        var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", request.LegalEntityId, "counterparties.common.edit", ct);
        if (grant is null) return Results.StatusCode(403);
        var name = request.LegalName?.Trim();
        var fiscal = request.FiscalIdentifier?.Trim();
        var office = request.RegisteredOffice?.Trim();
        if (string.IsNullOrEmpty(name) || name.Length > 200 || string.IsNullOrEmpty(fiscal) || fiscal.Length > 100 || string.IsNullOrEmpty(office) || office.Length > 500) return Results.BadRequest();
        await using var tx = await DestinationEndpoints.Begin(db, grant, request.LegalEntityId, ct);
        var row = await db.Counterparties.SingleOrDefaultAsync(x => x.Id == id, ct);
        if (row is null) return Results.NotFound();
        row.LegalName = name;
        row.FiscalIdentifier = fiscal;
        row.RegisteredOffice = office;
        await db.SaveChangesAsync(ct);
        await tx.CommitAsync(ct);
        return Results.Ok(new CounterpartyContract(row.Id, row.TenantId, row.LegalName, row.FiscalIdentifier, row.RegisteredOffice));
    }
}
