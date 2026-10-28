using System.Security.Claims;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Catalog;

// D91 list maintenance only. No intent pricing, dispatch, sales-price fallback or ERP identity.
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
internal sealed record SupplierPurchasePriceRequest(Guid LegalEntityId, Guid CommandId, int? ExpectedRevision,
    int? SupplierRevision, int? CatalogVersion, int? AuthorityVersion, string? UnitPurchasePrice);

internal static class PurchasePriceEndpoints
{
    internal static void Map(WebApplication app)
    {
        var routes = app.MapGroup("/api/v1/catalog/suppliers/{supplierId:guid}/items/{itemId:guid}/purchase-price").RequireAuthorization();
        routes.MapGet("", Read);
        routes.MapPut("", Save);
    }
    private static async Task<IResult> Read(Guid supplierId, Guid itemId, Guid legalEntityId, ClaimsPrincipal user, CatalogDbContext db, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await Context(db, user, ct);
        var json = await db.Database.SqlQuery<string>($"SELECT catalog.supplier_purchase_price_state({legalEntityId},{supplierId},{itemId})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return Result(json);
    }
    private static async Task<IResult> Save(Guid supplierId, Guid itemId, SupplierPurchasePriceRequest request, ClaimsPrincipal user, CatalogDbContext db, CancellationToken ct)
    {
        if (request.LegalEntityId == Guid.Empty || request.CommandId == Guid.Empty || supplierId == Guid.Empty || itemId == Guid.Empty
            || request.ExpectedRevision is not >= 0 || request.SupplierRevision is not >= 0 || request.CatalogVersion is not > 0 || request.AuthorityVersion is not > 0
            || request.UnitPurchasePrice is not { Length: > 0 and <= 13 }) return Results.BadRequest();
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await Context(db, user, ct);
        var json = await db.Database.SqlQuery<string>($"SELECT catalog.set_supplier_purchase_price({request.LegalEntityId},{supplierId},{itemId},{request.CommandId},{request.ExpectedRevision.Value},{request.SupplierRevision.Value},{request.CatalogVersion.Value},{request.AuthorityVersion.Value},{request.UnitPurchasePrice})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return Result(json);
    }
    private static Task Context(CatalogDbContext db, ClaimsPrincipal user, CancellationToken ct) =>
        db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject',{user.FindFirstValue(ClaimTypes.NameIdentifier) ?? ""},true),set_config('app.tenant_id','',true),set_config('app.legal_entity_id','',true)", ct);
    private static IResult Result(string value)
    {
        var json = JsonSerializer.Deserialize<JsonElement>(value);
        return Results.Json(json, statusCode: json.GetProperty("state").GetString() switch
        {
            "ready" or "replayed" => 200, "applied" => 201, "forbidden" => 403,
            "not_found" => 404, "invalid" => 400, _ => 409
        });
    }
}
