using System.Security.Claims;
using Enginia360.Counterparties.Domain;
using Enginia360.Counterparties.Infrastructure;
using Enginia360.Counterparties.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
namespace Enginia360.Counterparties;
internal static class CommonEndpoints
{
    internal static async Task<IResult> Authority(Guid legalEntityId, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct)
    {
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var grant = await access.Authorize(subject, legalEntityId, "counterparties.read", ct);
        if (grant is null) return Results.StatusCode(403);
        await using var tx = await DestinationEndpoints.Begin(db, grant, legalEntityId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var json = await db.Database.SqlQuery<string>($"SELECT organization_access.read_master_authority({legalEntityId})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return JsonResult(json, write: false);
    }

    internal static async Task<IResult> EditState(Guid id, Guid legalEntityId, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, CancellationToken ct)
    {
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var grant = await access.Authorize(subject, legalEntityId, "counterparties.read", ct);
        if (grant is null) return Results.StatusCode(403);
        await using var tx = await DestinationEndpoints.Begin(db, grant, legalEntityId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var json = await db.Database.SqlQuery<string>($"SELECT counterparties.common_edit_state({legalEntityId},{id})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return JsonResult(json);
    }

    internal static IResult JsonResult(string json, bool write = true)
    {
        using var parsed = System.Text.Json.JsonDocument.Parse(json);
        var state = parsed.RootElement.GetProperty("state").GetString();
        var status = state switch
        {
            "forbidden" => 403,
            "not_found" => 404,
            "invalid" => 400,
            "conflict" or "stale_authority" or "external" or "missing" when write => 409,
            _ => 200
        };
        return Results.Content(json, "application/json", statusCode: status);
    }
    internal static async Task<IResult> Update(Guid id, UpdateCounterpartyRequest request, ClaimsPrincipal user, ICounterpartyAccess access, CounterpartiesDbContext db, IConfiguration configuration, CancellationToken ct)
    {
        var grant = await access.Authorize(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", request.LegalEntityId, "counterparties.common.edit", ct);
        if (grant is null) return Results.StatusCode(403);
        var name = request.LegalName?.Trim();
        var fiscal = request.FiscalIdentifier?.Trim();
        var office = request.RegisteredOffice?.Trim();
        if (string.IsNullOrEmpty(name) || name.Length > 200 || string.IsNullOrEmpty(fiscal) || fiscal.Length > 100 || string.IsNullOrEmpty(office) || office.Length > 500) return Results.BadRequest();
        await using var tx = await DestinationEndpoints.Begin(db, grant, request.LegalEntityId, ct);
        if (configuration["Authentication:Profile"] != "SyntheticLegacy" || configuration.GetValue<bool>("BrowserSessions:Enabled"))
        {
            if (request.CommandId is not Guid commandId || commandId == Guid.Empty || request.AuthorityVersion is not int authorityVersion || authorityVersion < 0 || request.ExpectedRevision is not int expectedRevision || expectedRevision < 0) return Results.BadRequest();
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {user.FindFirstValue(ClaimTypes.NameIdentifier) ?? ""}, true)", ct);
            var json = await db.Database.SqlQuery<string>($"SELECT counterparties.edit_common({request.LegalEntityId},{id},{commandId},{authorityVersion},{expectedRevision},{name},{fiscal},{office})::text AS \"Value\"").SingleAsync(ct);
            await tx.CommitAsync(ct);
            return JsonResult(json);
        }
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
