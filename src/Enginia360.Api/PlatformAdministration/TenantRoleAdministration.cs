using System.Data.Common;
using System.Text.Json;
using Enginia360.Api.OrganizationAccess;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.PlatformAdministration;

public static class TenantRoleAdministration
{
    public static void MapTenantRoleAdministration(this WebApplication app)
    {
        var group = app.MapGroup("/api/v1/platform/tenant-roles").RequireAuthorization();
        group.MapGet("/workspace", (HttpContext context, OrganizationAccessDbContext db, CancellationToken ct)
            => Execute(context, db, null, ct));
        group.MapGet("/{tenantId:guid}", (Guid tenantId, HttpContext context, OrganizationAccessDbContext db, CancellationToken ct)
            => Execute(context, db, tenantId, ct));
        group.MapPost("/{tenantId:guid}", (Guid tenantId, HttpContext context, OrganizationAccessDbContext db, CancellationToken ct)
            => Command(context, db, tenantId, ct));
    }

    private static bool ValidJson(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Object => value.EnumerateObject().Select(p => p.Name).Distinct(StringComparer.Ordinal).Count()
            == value.EnumerateObject().Count() && value.EnumerateObject().All(p => !p.Name.Contains('\0') && ValidJson(p.Value)),
        JsonValueKind.Array => value.GetArrayLength() <= 64 && value.EnumerateArray().All(ValidJson),
        JsonValueKind.String => !value.GetString()!.Contains('\0'),
        JsonValueKind.Number => value.TryGetInt32(out var revision) && revision is >= 0 and <= 2147483646,
        JsonValueKind.Null or JsonValueKind.True or JsonValueKind.False => true,
        _ => false,
    };

    private static async Task<IResult> Command(HttpContext context, OrganizationAccessDbContext db,
        Guid target, CancellationToken ct)
    {
        context.Response.Headers.CacheControl = "no-store";
        var buffer = new byte[16385];
        var count = 0;
        while (count < buffer.Length)
        {
            var read = await context.Request.Body.ReadAsync(buffer.AsMemory(count), ct);
            if (read == 0) break;
            count += read;
        }
        if (count > 16384) return Results.BadRequest(new { state = "invalid" });
        try
        {
            using var document = JsonDocument.Parse(buffer.AsMemory(0, count), new JsonDocumentOptions { MaxDepth = 8 });
            if (document.RootElement.ValueKind != JsonValueKind.Object || !ValidJson(document.RootElement))
                return Results.BadRequest(new { state = "invalid" });
            return await Execute(context, db, target, ct, document.RootElement.GetRawText());
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException)
        {
            return Results.BadRequest(new { state = "invalid" });
        }
    }

    private static async Task<IResult> Execute(HttpContext context, OrganizationAccessDbContext db,
        Guid? target, CancellationToken ct, string? request = null)
    {
        context.Response.Headers.CacheControl = "no-store";
        var actor = VerifiedActorContext.FromPrincipal(context.User);
        if (actor is null) return Results.StatusCode(403);
        try
        {
            await using var transaction = await db.Database.BeginTransactionAsync(ct);
            await db.Database.ExecuteSqlInterpolatedAsync($"""
                SELECT set_config('app.identity_subject', {actor.InternalIdentityId.ToString("D")}, true),
                    set_config('app.identity_issuer', {actor.Issuer}, true),
                    set_config('app.external_subject', {actor.Subject}, true)
                """, ct);
            var json = request is null ? await db.Database.SqlQuery<string>($"""
                SELECT organization_access.read_tenant_roles({target}::uuid)::text AS "Value"
                """).SingleAsync(ct) : await db.Database.SqlQuery<string>($"""
                SELECT organization_access.command_tenant_role({target}::uuid,{request}::jsonb)::text AS "Value"
                """).SingleAsync(ct);
            using var document = JsonDocument.Parse(json);
            var state = document.RootElement.GetProperty("state").GetString();
            await transaction.CommitAsync(ct);
            return Results.Content(json, "application/json", statusCode: state switch
            {
                "ok" or "applied" or "replayed" => 200,
                "invalid" => 400,
                "conflict" => 409,
                "forbidden" => 403,
                _ => 503,
            });
        }
        catch (Exception error) when (error is DbException or TimeoutException)
        {
            return Results.Json(new { error = "store_unavailable" }, statusCode: 503);
        }
    }
}
