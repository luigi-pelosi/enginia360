using System.Data.Common;
using System.Text.Json;
using Enginia360.Api.OrganizationAccess;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.PlatformAdministration;

public static class OrganizationAdministration
{
    public static void MapOrganizationAdministration(this WebApplication app)
    {
        var group = app.MapGroup("/api/v1/platform/tenants").RequireAuthorization();
        group.MapGet("", (HttpContext context, OrganizationAccessDbContext db, CancellationToken ct)
            => Execute(context, db, null, ct));
        group.MapGet("/workspace", (HttpContext context, OrganizationAccessDbContext db, CancellationToken ct)
            => Execute(context, db, null, ct, workspace: true));
        group.MapGet("/{tenantId:guid}", (Guid tenantId, HttpContext context,
            OrganizationAccessDbContext db, CancellationToken ct) => Execute(context, db, tenantId, ct));
        group.MapPost("", (HttpContext context, OrganizationAccessDbContext db, CancellationToken ct)
            => Command(context, db, null, ct));
        group.MapGet("/{tenantId:guid}/delegations", (Guid tenantId, HttpContext context,
            OrganizationAccessDbContext db, CancellationToken ct) => Execute(context, db, tenantId, ct, delegations: true));
        group.MapPost("/{tenantId:guid}/delegations", (Guid tenantId, HttpContext context,
            OrganizationAccessDbContext db, CancellationToken ct) => Command(context, db, tenantId, ct, true));
        group.MapPost("/{tenantId:guid}/commands", (Guid tenantId, HttpContext context,
            OrganizationAccessDbContext db, CancellationToken ct) => Command(context, db, tenantId, ct));
    }

    private static async Task<IResult> Command(HttpContext context, OrganizationAccessDbContext db,
        Guid? target, CancellationToken ct, bool delegations = false)
    {
        context.Response.Headers.CacheControl = "no-store";
        // Bounded streaming parse also protects requests without Content-Length.
        var buffer = new byte[16385];
        var count = 0;
        while (count < buffer.Length)
        {
            var read = await context.Request.Body.ReadAsync(buffer.AsMemory(count), ct);
            if (read == 0) break;
            count += read;
        }
        if (count > 16384) return Results.BadRequest(new { state = "invalid" });
        string request;
        try
        {
            using var document = JsonDocument.Parse(buffer.AsMemory(0, count),
                new JsonDocumentOptions { MaxDepth = 8 });
            var root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
                return Results.BadRequest(new { state = "invalid" });
            var properties = root.EnumerateObject().ToArray();
            if (properties.Select(p => p.Name).Distinct(StringComparer.Ordinal).Count() != properties.Length
                || properties.Any(p => p.Name.Contains('\0')
                    || p.Value.ValueKind is not (JsonValueKind.String or JsonValueKind.Number or JsonValueKind.Null)
                    || p.Value.ValueKind == JsonValueKind.String && p.Value.GetString()!.Contains('\0')))
                return Results.BadRequest(new { state = "invalid" });
            request = root.GetRawText();
        }
        catch (Exception error) when (error is JsonException or InvalidOperationException)
        {
            // InvalidOperationException here means an unpaired escaped UTF-16 surrogate.
            return Results.BadRequest(new { state = "invalid" });
        }
        return await Execute(context, db, target, ct, request, delegations);
    }

    private static async Task<IResult> Execute(HttpContext context, OrganizationAccessDbContext db,
        Guid? target, CancellationToken ct, string? request = null, bool delegations = false, bool workspace = false)
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
            var json = workspace
                ? await db.Database.SqlQuery<string>($"""
                    SELECT organization_access.read_organization_workspace()::text AS "Value"
                    """).SingleAsync(ct)
                : delegations && request is not null
                ? await db.Database.SqlQuery<string>($"""
                    SELECT organization_access.command_organization_delegation({target}::uuid,{request}::jsonb)::text AS "Value"
                    """).SingleAsync(ct)
                : delegations
                ? await db.Database.SqlQuery<string>($"""
                    SELECT organization_access.read_organization_delegations({target}::uuid)::text AS "Value"
                    """).SingleAsync(ct)
                : request is null
                ? await db.Database.SqlQuery<string>($"""
                    SELECT organization_access.read_organization({target}::uuid)::text AS "Value"
                    """).SingleAsync(ct)
                : await db.Database.SqlQuery<string>($"""
                    SELECT organization_access.command_organization({target}::uuid,{request}::jsonb)::text AS "Value"
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
                "not_found" => 404,
                _ => 503,
            });
        }
        catch (Exception error) when (error is DbException or TimeoutException)
        {
            return Results.Json(new { error = "store_unavailable" }, statusCode: 503);
        }
    }
}
