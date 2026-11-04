using Enginia360.Catalog.Contracts;
using System.Data.Common;
using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Catalog;

// The owning module rechecks exact identity, state and current permission inside
// the same physical transaction as the mutation/audit. No cached menu grants.
internal static class ManagementEndpoints
{
    internal static void Map(WebApplication app)
    {
        var management = app.MapGroup("/api/v1/catalog/management").RequireAuthorization().AddEndpointFilter(async (context, next) =>
        {
            context.HttpContext.Response.Headers.CacheControl = "private, no-store";
            context.HttpContext.Response.Headers.Vary = "Cookie, Authorization";
            return await next(context);
        });
        management.MapGet("", Read);
        management.MapPost("/commands", Command);
    }

    private static bool Uuid(string? value, out Guid? id)
    {
        id = null;
        if (value is null) return true;
        if (!Guid.TryParseExact(value, "D", out var parsed) || parsed == Guid.Empty || parsed.ToString("D") != value) return false;
        id = parsed;
        return true;
    }

    private static async Task<IResult> Read(HttpContext context, CatalogDbContext db, CancellationToken ct)
    {
        if (context.Request.Query.Any(x => !new[] { "search", "after", "id", "kind" }.Contains(x.Key) || x.Value.Count != 1)
            || !Uuid(context.Request.Query["after"].FirstOrDefault(), out var after)
            || !Uuid(context.Request.Query["id"].FirstOrDefault(), out var id)
            || context.Request.Query["kind"].FirstOrDefault() is { } kind && kind is not ("" or "Article" or "Service"))
            return Results.BadRequest(new { state = "invalid" });
        return await Execute(context, db, ct, search: context.Request.Query["search"].FirstOrDefault(), after: after, id: id, kind: string.IsNullOrEmpty(context.Request.Query["kind"].FirstOrDefault()) ? null : context.Request.Query["kind"].FirstOrDefault());
    }

    private static bool ValidJson(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Object => value.EnumerateObject().Select(x => x.Name).Distinct(StringComparer.Ordinal).Count() == value.EnumerateObject().Count()
            && value.EnumerateObject().All(x => !x.Name.Contains('\0') && ValidJson(x.Value)),
        JsonValueKind.String => !value.GetString()!.Contains('\0'),
        JsonValueKind.Number => value.TryGetInt32(out var revision) && revision >= 0,
        JsonValueKind.Null or JsonValueKind.True or JsonValueKind.False => true,
        _ => false,
    };

    private static async Task<IResult> Command(HttpContext context, CatalogDbContext db, CancellationToken ct)
    {
        var bytes = new byte[8193];
        var count = 0;
        while (count < bytes.Length)
        {
            var read = await context.Request.Body.ReadAsync(bytes.AsMemory(count), ct);
            if (read == 0) break;
            count += read;
        }
        if (count > 8192) return Results.BadRequest(new { state = "invalid" });
        try
        {
            using var document = JsonDocument.Parse(bytes.AsMemory(0, count), new JsonDocumentOptions { MaxDepth = 3 });
            if (document.RootElement.ValueKind != JsonValueKind.Object || !ValidJson(document.RootElement)) return Results.BadRequest(new { state = "invalid" });
            var command = document.RootElement.Deserialize<CatalogManagementCommand>(new JsonSerializerOptions(JsonSerializerDefaults.Web));
            if (command is null || !Enum.IsDefined(command.Kind)) return Results.BadRequest(new { state = "invalid" });
            // SQL validates exact keys/types again; preserve the original typed payload for replay.
            return await Execute(context, db, ct, request: document.RootElement.GetRawText());
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException)
        { return Results.BadRequest(new { state = "invalid" }); }
    }

    private static async Task<IResult> Execute(HttpContext context, CatalogDbContext db, CancellationToken ct,
        string? request = null, string? search = null, Guid? after = null, Guid? id = null, string? kind = null)
    {
        context.Response.Headers.CacheControl = "private, no-store";
        context.Response.Headers.Vary = "Cookie, Authorization";
        var principal = context.User;
        var internalId = principal.FindFirstValue(ClaimTypes.NameIdentifier);
        var issuer = principal.FindFirstValue("enginia360:verified-issuer");
        var subject = principal.FindFirstValue("enginia360:external-subject");
        if (principal.Identity?.IsAuthenticated != true || !Guid.TryParseExact(internalId, "D", out var actor) || actor == Guid.Empty
            || string.IsNullOrEmpty(issuer) || string.IsNullOrEmpty(subject)) return Results.StatusCode(403);
        try
        {
            await using var tx = await db.Database.BeginTransactionAsync(ct);
            await db.Database.ExecuteSqlInterpolatedAsync($"""
                SELECT set_config('app.identity_subject', {actor.ToString("D")}, true),
                 set_config('app.identity_issuer', {issuer}, true), set_config('app.external_subject', {subject}, true),
                 set_config('app.tenant_id', '', true), set_config('app.legal_entity_id', '', true)
                """, ct);
            var json = request is null
                ? await db.Database.SqlQuery<string>($"SELECT catalog.management_read({search}::text,{after}::uuid,{id}::uuid,{kind}::text)::text AS \"Value\"").SingleAsync(ct)
                : await db.Database.SqlQuery<string>($"SELECT catalog.management_command({request}::jsonb)::text AS \"Value\"").SingleAsync(ct);
            await tx.CommitAsync(ct);
            using var result = JsonDocument.Parse(json);
            return Results.Content(json, "application/json", statusCode: result.RootElement.GetProperty("state").GetString() switch
            {
                "ready" or "replayed" => 200, "applied" => 201,
                "invalid" => 400, "forbidden" => 403, "not_found" => 404, _ => 409,
            });
        }
        catch (Exception error) when (error is DbException or TimeoutException)
        {
            return Results.Json(new { state = "store_unavailable" }, statusCode: 503);
        }
    }
}
