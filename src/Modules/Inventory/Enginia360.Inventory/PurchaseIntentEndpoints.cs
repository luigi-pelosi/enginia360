using System.Security.Claims;
using System.Text.Json;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Inventory;

internal static class PurchaseIntentEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapGet("/orders/{orderId:guid}/lines/{lineId:guid}/purchase-intents", Read);
        routes.MapPost("/orders/{orderId:guid}/lines/{lineId:guid}/purchase-intents", Create);
    }
    private static async Task<IResult> Read(Guid orderId, Guid lineId, Guid warehouseId, ClaimsPrincipal user,
        IWorkshopAccess access, InventoryDbContext db, CancellationToken ct)
    {
        var member = await access.ResolveMembership(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", ct);
        if (member is null) return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await Context(db, member.TenantId, user, ct);
        var value = await db.Database.SqlQuery<string>($"SELECT inventory.purchase_intent_state({orderId},{lineId},{warehouseId})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return Result(value);
    }
    private static async Task<IResult> Create(Guid orderId, Guid lineId, PurchaseIntentRequest request, ClaimsPrincipal user,
        IWorkshopAccess access, InventoryDbContext db, IServiceProvider services, CancellationToken ct)
    {
        if (orderId == Guid.Empty || lineId == Guid.Empty || request.Id == Guid.Empty || request.WarehouseId == Guid.Empty
            || request.SupplierId == Guid.Empty || request.SourceRevision is not > 0 || request.SupplierRevision is not >= 0
            || request.MappingRevision is not > 0 || request.Quantity is not { Length: > 0 and <= 13 }) return Results.BadRequest();
        var member = await access.ResolveMembership(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", ct);
        if (member is null) return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await Context(db, member.TenantId, user, ct);
        var destination = services.GetService<PurchaseDestinationBinding>();
        var descriptor = destination?.Descriptor ?? "{}";
        var value = await db.Database.SqlQuery<string>($"SELECT inventory.create_purchase_intent({request.Id},{orderId},{lineId},{request.WarehouseId},{request.SupplierId},{request.SourceRevision.Value},{request.SupplierRevision.Value},{request.MappingRevision.Value},{request.Quantity},CAST({descriptor} AS jsonb))::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return Result(value);
    }
    private static async Task Context(InventoryDbContext db, Guid tenant, ClaimsPrincipal user, CancellationToken ct)
    {
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{tenant.ToString()},true),set_config('app.identity_subject',{user.FindFirstValue(ClaimTypes.NameIdentifier) ?? ""},true)", ct);
    }
    private static IResult Result(string value)
    {
        var json = JsonSerializer.Deserialize<JsonElement>(value);
        var state = json.GetProperty("state").GetString();
        var status = state switch { "ready" or "replayed" => 200, "applied" => 201, "forbidden" => 403, "not_found" => 404, "invalid" => 400, _ => 409 };
        return Results.Json(json, statusCode: status);
    }
}
