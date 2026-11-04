using System.Security.Claims;
using System.Text.Json;
using Enginia360.Api.OrganizationAccess;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.BrowserAuthentication;

// NEVER selected by browser-or-bearer. Contains no application identity or grants.
public static class PendingOnboarding
{
    public const string Scheme = "pending-onboarding";
    public const string RequestClaim = "enginia360:pending-request";
    public const string TenantClaim = "enginia360:pending-tenant";

    public static async Task<bool> Receive(HttpContext context, string issuer, string subject, Guid invitation)
    {
        if (!ExternalIdentityResolver.IsValidExternalIdentity(issuer, subject)) return false;
        var db = context.RequestServices.GetRequiredService<OrganizationAccessDbContext>();
        var ct = context.RequestAborted;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetProof(db, issuer, subject, ct);
        var json = await db.Database.SqlQuery<string>($"""
            SELECT organization_access.begin_onboarding({invitation})::text AS "Value"
            """).SingleAsync(ct);
        using var result = JsonDocument.Parse(json);
        if (result.RootElement.GetProperty("state").GetString() != "ok") return false;
        var id = result.RootElement.GetProperty("requestId").GetGuid().ToString("D");
        var tenant = result.RootElement.GetProperty("tenantId").GetGuid().ToString("D");
        var expires = result.RootElement.GetProperty("expiresAt").GetDateTimeOffset();
        await tx.CommitAsync(ct);
        // Remove any old ordinary session: the two identities must never be combined.
        await context.SignOutAsync("browser");
        await context.SignOutAsync(Scheme);
        await context.SignInAsync(Scheme, new ClaimsPrincipal(new ClaimsIdentity([
            new("sub", id), new(RequestClaim, id), new(TenantClaim, tenant),
            new(ExternalIdentityResolver.IssuerClaim, issuer),
            new(ExternalIdentityResolver.SubjectClaim, subject)], Scheme)),
            new AuthenticationProperties { IsPersistent = false, ExpiresUtc = expires, AllowRefresh = false });
        return true;
    }

    private static Task<int> SetProof(OrganizationAccessDbContext db, string issuer, string subject, CancellationToken ct)
        => db.Database.ExecuteSqlInterpolatedAsync($"""
            SELECT set_config('app.identity_subject', '', true),
                set_config('app.identity_issuer', {issuer}, true), set_config('app.external_subject', {subject}, true)
            """, ct);

    public static WebApplication UsePendingOnboarding(this WebApplication app)
    {
        if (!app.Configuration.GetValue<bool>("BrowserSessions:Enabled")) return app;
        app.Use(async (context, next) =>
        {
            // Only these auth endpoints use the isolated ticket. Never ordinary APIs or /auth/session.
            var path = context.Request.Path.Value?.TrimEnd('/');
            if (string.Equals(path, "/auth/onboarding/status", StringComparison.OrdinalIgnoreCase)
                || string.Equals(path, "/auth/onboarding/csrf", StringComparison.OrdinalIgnoreCase)
                || string.Equals(path, "/auth/onboarding/logout", StringComparison.OrdinalIgnoreCase))
            {
                context.User = new ClaimsPrincipal(new ClaimsIdentity());
                if (!context.Request.Headers.ContainsKey("Authorization"))
                {
                    var auth = await context.AuthenticateAsync(Scheme);
                    if (auth.Succeeded && auth.Principal is not null) context.User = auth.Principal;
                }
            }
            await next(context);
        });
        return app;
    }

    public static void MapPendingOnboarding(this WebApplication app)
    {
        if (!app.Configuration.GetValue<bool>("BrowserSessions:Enabled")) return;
        app.MapPost("/auth/onboarding/login/{invitation:guid}", (Guid invitation) =>
            invitation == Guid.Empty ? (IResult)Results.BadRequest() : Results.Challenge(
                new AuthenticationProperties(new Dictionary<string, string?> { ["onboarding-invitation"] = invitation.ToString("D") })
                { RedirectUri = "/onboarding" }, ["oidc"]));
        app.MapGet("/auth/onboarding/csrf", (HttpContext context, IAntiforgery antiforgery) =>
            context.User.Identity?.AuthenticationType != Scheme ? (IResult)Results.Unauthorized()
                : Results.Ok(new { requestToken = antiforgery.GetAndStoreTokens(context).RequestToken }));
        app.MapPost("/auth/onboarding/logout", async (HttpContext context) =>
        {
            await context.SignOutAsync(Scheme);
            return Results.Redirect("/onboarding");
        });
        app.MapGet("/auth/onboarding/status", async (HttpContext context, OrganizationAccessDbContext db, CancellationToken ct) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            var principal = context.User;
            if (principal.Identity?.AuthenticationType != Scheme
                || !Guid.TryParseExact(principal.FindFirstValue(RequestClaim), "D", out var id)
                || !Guid.TryParseExact(principal.FindFirstValue(TenantClaim), "D", out var tenant)
                || principal.FindFirstValue(ExternalIdentityResolver.IssuerClaim) is not { } issuer
                || principal.FindFirstValue(ExternalIdentityResolver.SubjectClaim) is not { } subject)
                return Results.Unauthorized();
            await using var tx = await db.Database.BeginTransactionAsync(ct);
            await SetProof(db, issuer, subject, ct);
            var json = await db.Database.SqlQuery<string>($"""
                SELECT organization_access.pending_onboarding_status({id},{tenant})::text AS "Value"
                """).SingleAsync(ct);
            using var result = JsonDocument.Parse(json);
            await tx.CommitAsync(ct);
            return Results.Content(json, "application/json", statusCode: result.RootElement.GetProperty("state").GetString() == "ok" ? 200 : 403);
        });
    }
}
