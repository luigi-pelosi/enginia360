using System.Security.Claims;
using Enginia360.Counterparties.Infrastructure;
using Enginia360.Counterparties.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
namespace Enginia360.Counterparties;

// D88: supplier is a role of the tenant-wide shared master (same exact grants, authority and revision as the common edit);
// the Giobby vendor identity is a read-only company extension written only by the owner path.
internal static class SupplierEndpoints
{
    private static bool RuntimeProfile(IConfiguration configuration) =>
        configuration["Authentication:Profile"] != "SyntheticLegacy" || configuration.GetValue<bool>("BrowserSessions:Enabled");

    internal static async Task<IResult> SetRole(Guid id, SupplierRoleRequest request, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, IConfiguration configuration, CancellationToken ct)
    {
        if (!RuntimeProfile(configuration)) return Results.NotFound();
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var grant = await access.Authorize(subject, request.LegalEntityId, "counterparties.common.edit", ct);
        if (grant is null) return Results.StatusCode(403);
        if (request.CommandId is not Guid commandId || commandId == Guid.Empty || request.AuthorityVersion is not int authorityVersion || authorityVersion < 0 || request.ExpectedRevision is not int expectedRevision || expectedRevision < 0 || request.IsSupplier is not bool isSupplier) return Results.BadRequest();
        await using var tx = await DestinationEndpoints.Begin(db, grant, request.LegalEntityId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var json = await db.Database.SqlQuery<string>($"SELECT counterparties.set_supplier_role({request.LegalEntityId},{id},{commandId},{authorityVersion},{expectedRevision},{isSupplier})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return CommonEndpoints.JsonResult(json);
    }

    internal static async Task<IResult> ReadErpIdentity(Guid id, Guid legalEntityId, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, IConfiguration configuration, CancellationToken ct)
    {
        if (!RuntimeProfile(configuration)) return Results.NotFound();
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var grant = await access.Authorize(subject, legalEntityId, "counterparties.read", ct);
        if (grant is null) return Results.StatusCode(403);
        await using var tx = await DestinationEndpoints.Begin(db, grant, legalEntityId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var json = await db.Database.SqlQuery<string>($"SELECT counterparties.read_giobby_vendor_identity({legalEntityId},{id})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return CommonEndpoints.JsonResult(json, write: false);
    }
}
