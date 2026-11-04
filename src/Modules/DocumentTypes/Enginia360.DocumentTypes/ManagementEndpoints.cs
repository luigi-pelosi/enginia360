using Enginia360.DocumentTypes.Contracts;
using System.Data.Common;
using System.Globalization;
using System.Security.Claims;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.DocumentTypes;

internal static class ManagementEndpoints
{
    internal static void Map(WebApplication app)
    {
        var routes = app.MapGroup("/api/v1/document-types").RequireAuthorization();
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
    private static bool Revision(string? value, out int? revision)
    {
        revision = null;
        if (value is null) return true;
        if (!int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var parsed) || parsed < 1 || parsed.ToString(CultureInfo.InvariantCulture) != value) return false;
        revision = parsed; return true;
    }
    private static Task<IResult> Read(HttpContext context, DocumentTypesDbContext db, CancellationToken ct)
    {
        var query = context.Request.Query;
        if (query.Any(x => !new[] { "legalEntityId", "search", "after", "id", "revision", "beforeRevision" }.Contains(x.Key) || x.Value.Count != 1)
            || !Uuid(query["legalEntityId"].FirstOrDefault(), out var company)
            || !Uuid(query["after"].FirstOrDefault(), out var after)
            || !Uuid(query["id"].FirstOrDefault(), out var id)
            || !Revision(query["revision"].FirstOrDefault(), out var revision)
            || !Revision(query["beforeRevision"].FirstOrDefault(), out var before))
            return Task.FromResult<IResult>(Results.BadRequest(new { state = "invalid" }));
        var search = query["search"].FirstOrDefault();
        if (search is not null && (search.EnumerateRunes().Count() > 200 || search.Any(char.IsControl)))
            return Task.FromResult<IResult>(Results.BadRequest(new { state = "invalid" }));
        return Execute(context, db, ct, company: company, search: search, after: after, id: id, revision: revision, before: before);
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
    private static async Task<IResult> Command(HttpContext context, DocumentTypesDbContext db, CancellationToken ct)
    {
        var bytes = new byte[8193]; var count = 0;
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
            var command = document.RootElement.Deserialize<DocumentTypeCommand>(new JsonSerializerOptions(JsonSerializerDefaults.Web));
            if (command is null || !Enum.IsDefined(command.Effect)) return Results.BadRequest(new { state = "invalid" });
            return await Execute(context, db, ct, request: document.RootElement.GetRawText());
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException or ArgumentException)
        { return Results.BadRequest(new { state = "invalid" }); }
    }
    private static async Task<IResult> Execute(HttpContext context, DocumentTypesDbContext db, CancellationToken ct,
        string? request = null, Guid? company = null, string? search = null, Guid? after = null, Guid? id = null, int? revision = null, int? before = null)
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
                ? await db.Database.SqlQuery<string>($"SELECT document_types.read({company}::uuid,{search}::text,{after}::uuid,{id}::uuid,{revision}::integer,{before}::integer)::text AS \"Value\"").SingleAsync(ct)
                : await db.Database.SqlQuery<string>($"SELECT document_types.command({request}::jsonb)::text AS \"Value\"").SingleAsync(ct);
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
