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

internal static class ReceiptIntentEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapPost("/purchase-intents/{sourceIntentId:guid}/receipts", Create);
        routes.MapGet("/purchase-intents/{sourceIntentId:guid}/receipts", Read);
    }
    private static async Task<IResult> Create(Guid sourceIntentId, ReceiptIntentRequest request, ClaimsPrincipal user,
        IWorkshopAccess access, InventoryDbContext db, IServiceProvider services, CancellationToken ct)
    {
        if (sourceIntentId == Guid.Empty || request.Id == Guid.Empty || request.Quantity is not { Length: > 0 and <= 13 }) return Results.BadRequest();
        var member = await access.ResolveMembership(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "", ct);
        if (member is null) return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await Context(db,member.TenantId,user,ct);
        var destination=services.GetService<ReceiptDestinationBinding>()?.Descriptor ?? "{}";
        var value=await db.Database.SqlQuery<string>($"SELECT inventory.create_receipt_intent({request.Id},{sourceIntentId},{request.Quantity},CAST({destination} AS jsonb))::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return Result(value);
    }
    private static async Task<IResult> Read(Guid sourceIntentId, ClaimsPrincipal user, IWorkshopAccess access, InventoryDbContext db, IServiceProvider services, CancellationToken ct)
    {
        var member=await access.ResolveMembership(user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "",ct);
        if (member is null) return Results.StatusCode(403);
        await using var tx=await db.Database.BeginTransactionAsync(ct);
        await Context(db,member.TenantId,user,ct);
        var value=await db.Database.SqlQuery<string>($"SELECT inventory.receipt_state({sourceIntentId})::text AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        await tx.DisposeAsync(); // Release Inventory's connection before the owning Integrations contract: pool1 is supported.
        if (System.Text.Json.Nodes.JsonNode.Parse(value) is System.Text.Json.Nodes.JsonObject state
            && state["state"]?.GetValue<string>() == "ready" && state["receipts"] is System.Text.Json.Nodes.JsonArray receipts)
        {
            var ids=receipts.Select(r=>Guid.Parse(r!["id"]!.GetValue<string>())).ToArray();
            var deliveries=ids.Length==0 || services.GetService<IReceiptDeliveries>() is not { } reader
                ? new Dictionary<Guid,ReceiptDelivery>() : await reader.Read(member.TenantId,ids,ct);
            ReceiptDispatchReadout.Apply(state,deliveries);
            return Result(state.ToJsonString());
        }
        return Result(value);
    }
    private static async Task Context(InventoryDbContext db,Guid tenant,ClaimsPrincipal user,CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{tenant.ToString()},true),set_config('app.identity_subject',{user.FindFirstValue(ClaimTypes.NameIdentifier) ?? ""},true)",ct);
    private static IResult Result(string value)
    {
        var json=JsonSerializer.Deserialize<JsonElement>(value);
        return Results.Json(json,statusCode:json.GetProperty("state").GetString() switch {
            "ready" or "replayed"=>200,"applied"=>201,"forbidden"=>403,"not_found"=>404,"invalid"=>400,_=>409 });
    }
}
