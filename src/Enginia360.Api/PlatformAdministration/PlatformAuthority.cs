using System.Data.Common;
using System.Security.Claims;
using Enginia360.Api.BrowserAuthentication;
using Enginia360.Api.OrganizationAccess;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.PlatformAdministration;

// Constructed only from the handler-resolved principal, never a request DTO.
public sealed record VerifiedActorContext(Guid InternalIdentityId, string Issuer, string Subject)
{
    public static VerifiedActorContext? FromPrincipal(ClaimsPrincipal principal)
    {
        var issuer = principal.FindFirstValue(ExternalIdentityResolver.IssuerClaim);
        var subject = principal.FindFirstValue(ExternalIdentityResolver.SubjectClaim);
        var internalId = principal.FindFirstValue(ClaimTypes.NameIdentifier);
        return principal.Identity?.IsAuthenticated == true
            && issuer is not null && subject is not null
            && ExternalIdentityResolver.IsValidExternalIdentity(issuer, subject)
            && Guid.TryParseExact(internalId, "D", out var identity) && identity != Guid.Empty
            ? new(identity, issuer, subject) : null;
    }
}

public static class PlatformAuthority
{
    public static WebApplication MapPlatformAuthority(this WebApplication app)
    {
        app.MapOrganizationAdministration();
        app.MapGet("/api/v1/platform/administration-eligibility", ReadEligibility)
            .RequireAuthorization();
        return app;
    }

    private static async Task<IResult> ReadEligibility(
        HttpContext context, OrganizationAccessDbContext db, CancellationToken cancellationToken)
    {
        context.Response.Headers.CacheControl = "no-store";
        var actor = VerifiedActorContext.FromPrincipal(context.User);
        if (actor is null)
            return Results.StatusCode(StatusCodes.Status403Forbidden);
        try
        {
            await using var transaction = await db.Database.BeginTransactionAsync(cancellationToken);
            await db.Database.ExecuteSqlInterpolatedAsync($"""
                SELECT set_config('app.identity_subject', {actor.InternalIdentityId.ToString("D")}, true),
                    set_config('app.identity_issuer', {actor.Issuer}, true),
                    set_config('app.external_subject', {actor.Subject}, true)
                """, cancellationToken);
            var eligible = await db.Database.SqlQuery<bool>($"""
                SELECT EXISTS (
                    SELECT 1 FROM organization_access.platform_authority a
                    JOIN organization_access.external_identity_bindings b
                        ON b."InternalIdentityId"=a."InternalIdentityId"
                        AND b."Issuer"=a."Issuer" AND b."Subject"=a."Subject"
                    WHERE a."Active" AND a."InternalIdentityId"={actor.InternalIdentityId}
                        AND a."Issuer"={actor.Issuer} COLLATE "C"
                        AND a."Subject"={actor.Subject} COLLATE "C"
                ) AS "Value"
                """).SingleAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
            return eligible ? Results.Ok(new PlatformEligibility(true))
                : Results.StatusCode(StatusCodes.Status403Forbidden);
        }
        catch (Exception error) when (error is DbException or TimeoutException)
        {
            return Results.Json(new { error = "store_unavailable" }, statusCode: 503);
        }
    }
}

public sealed record PlatformEligibility(bool CanAdministerPlatform);
