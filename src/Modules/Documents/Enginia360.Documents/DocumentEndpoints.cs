using System.Data.Common;
using System.Security.Claims;
using System.Text.Json;
using System.Text;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Documents;

internal static class DocumentEndpoints
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    internal static void Map(WebApplication app)
    {
        var routes = app.MapGroup("/api/v1/documents").RequireAuthorization();
        routes.MapGet("", Read);
        routes.MapPost("/commands", Command);
    }
    private static bool Uuid(string? value, out Guid? id)
    {
        id = null;
        if (value is null) return true;
        if (!Guid.TryParseExact(value, "D", out var parsed) || parsed == Guid.Empty || parsed.ToString("D") != value) return false;
        id = parsed; return true;
    }
    private static Task<IResult> Read(HttpContext context, DocumentsDbContext db, CancellationToken ct)
    {
        var q = context.Request.Query;
        if (q.Any(x => !new[] { "legalEntityId", "siteId", "warehouseId", "id", "search", "after", "selection", "selectionAfter", "ledgerAfter" }.Contains(x.Key) || x.Value.Count != 1)
            || !Uuid(q["legalEntityId"].FirstOrDefault(), out var company)
            || !Uuid(q["siteId"].FirstOrDefault(), out var site)
            || !Uuid(q["warehouseId"].FirstOrDefault(), out var warehouse)
            || !Uuid(q["id"].FirstOrDefault(), out var id)
            || !Uuid(q["after"].FirstOrDefault(), out var after)
            || !Uuid(q["selectionAfter"].FirstOrDefault(), out var selectionAfter)
            || !Uuid(q["ledgerAfter"].FirstOrDefault(), out var ledgerAfter))
            return Task.FromResult<IResult>(Results.BadRequest(new { state = "invalid" }));
        var search = q["search"].FirstOrDefault(); var selection = q["selection"].FirstOrDefault();
        if (search is not null && (search.EnumerateRunes().Count() > 200 || search.Any(char.IsControl))
            || selection is not null && selection is not ("catalog" or "types"))
            return Task.FromResult<IResult>(Results.BadRequest(new { state = "invalid" }));
        return Execute(context, db, ct, company, site, warehouse, id, search, after, selection, selectionAfter, ledgerAfter);
    }
    private static bool ValidJson(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Object => value.EnumerateObject().Select(x => x.Name).Distinct(StringComparer.Ordinal).Count() == value.EnumerateObject().Count()
            && value.EnumerateObject().All(x => !x.Name.Contains('\0') && ValidJson(x.Value)),
        JsonValueKind.Array => value.GetArrayLength() <= 200 && value.EnumerateArray().All(ValidJson),
        JsonValueKind.String => !value.GetString()!.Contains('\0'),
        JsonValueKind.Number => value.TryGetInt32(out var revision) && revision >= 0,
        JsonValueKind.Null or JsonValueKind.True or JsonValueKind.False => true,
        _ => false,
    };
    private static async Task<IResult> Command(HttpContext context, DocumentsDbContext db, CancellationToken ct)
    {
        // Bound the stream itself: Content-Length is absent for chunked requests.
        var bytes = new byte[262145]; var count = 0;
        while (count < bytes.Length)
        {
            var read = await context.Request.Body.ReadAsync(bytes.AsMemory(count), ct);
            if (read == 0) break;
            count += read;
        }
        if (count > 262144) return Results.BadRequest(new { state = "invalid" });
        try
        {
            using var document = JsonDocument.Parse(bytes.AsMemory(0, count), new JsonDocumentOptions { MaxDepth = 6 });
            var root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object || !ValidJson(root) || !root.TryGetProperty("operation", out var operation) || operation.ValueKind != JsonValueKind.String)
                return Results.BadRequest(new { state = "invalid" });
            object? command = operation.GetString() switch
            {
                "create" or "save" => root.Deserialize<SaveDocumentCommand>(JsonOptions),
                "confirm" => root.Deserialize<ConfirmDocumentCommand>(JsonOptions),
                "policy" => root.Deserialize<QuantityPolicyCommand>(JsonOptions),
                _ => null,
            };
            if (command is null) return Results.BadRequest(new { state = "invalid" });
            return await Execute(context, db, ct, request: root.GetRawText());
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException or ArgumentException)
        { return Results.BadRequest(new { state = "invalid" }); }
    }
    private static async Task<IResult> Execute(HttpContext context, DocumentsDbContext db, CancellationToken ct,
        Guid? company = null, Guid? site = null, Guid? warehouse = null, Guid? id = null,
        string? search = null, Guid? after = null, string? selection = null,
        Guid? selectionAfter = null, Guid? ledgerAfter = null, string? request = null)
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
                ? await db.Database.SqlQuery<string>($"SELECT documents.read({company}::uuid,{site}::uuid,{warehouse}::uuid,{id}::uuid,{search}::text,{after}::uuid,{selection}::text,{selectionAfter}::uuid,{ledgerAfter}::uuid)::text AS \"Value\"").SingleAsync(ct)
                : await db.Database.SqlQuery<string>($"SELECT documents.command({request}::jsonb)::text AS \"Value\"").SingleAsync(ct);
            await tx.CommitAsync(ct);
            using var result = JsonDocument.Parse(json);
            return Results.Content(json, "application/json", statusCode: result.RootElement.GetProperty("state").GetString() switch
            {
                "ready" or "replayed" => 200, "applied" => 201,
                "invalid" => 400, "forbidden" => 403, "not_found" => 404, _ => 409,
            });
        }
        catch (Exception error) when (error is DbException or TimeoutException)
        { return Results.Json(new { state = "store_unavailable" }, statusCode: 503); }
    }
}
