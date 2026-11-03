using Enginia360.Api.PlatformAdministration;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.OrganizationAccess;

// Identity propagation only. The adapter transaction is not the owning business
// effect transaction and must never be reported as an effect-serialization fence.
internal static class CompanyAccessIdentity
{
    internal static async Task Set(OrganizationAccessDbContext db, string subject,
        IHttpContextAccessor accessor, IConfiguration configuration, CancellationToken ct)
    {
        if (!(configuration["Authentication:Profile"] == "SyntheticLegacy"
            && !configuration.GetValue<bool>("BrowserSessions:Enabled")))
        {
            var actor = VerifiedActorContext.FromPrincipal(accessor.HttpContext?.User ?? new());
            if (actor is null || actor.InternalIdentityId.ToString("D") != subject)
                throw new InvalidOperationException("Verified current identity required.");
            await db.Database.ExecuteSqlInterpolatedAsync($"""
                SELECT set_config('app.identity_issuer', {actor.Issuer}, true),
                    set_config('app.external_subject', {actor.Subject}, true)
                """, ct);
        }
        await db.Database.ExecuteSqlInterpolatedAsync(
            $"SELECT set_config('app.identity_subject', {subject}, true)", ct);
    }
}
