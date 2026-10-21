using System.Security.Claims;
using Enginia360.Api.OrganizationAccess;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.BrowserAuthentication;

// This is a technical lookup, not identity provisioning or a source of business grants.
// Call only after the authentication handler has verified issuer, signature and token rules.
public sealed class ExternalIdentityResolver(OrganizationAccessDbContext db)
{
    public const string IssuerClaim = "enginia360:verified-issuer";
    public const string SubjectClaim = "enginia360:external-subject";

    public async Task<ClaimsPrincipal?> Resolve(
        string issuer,
        string subject,
        string authenticationType,
        CancellationToken cancellationToken
    )
    {
        if (!IsValidExternalIdentity(issuer, subject))
            return null;
        await using var transaction = await db.Database.BeginTransactionAsync(cancellationToken);
        await db.Database.ExecuteSqlInterpolatedAsync(
            $"SELECT set_config('app.identity_issuer', {issuer}, true), set_config('app.external_subject', {subject}, true)",
            cancellationToken);
        var identity = await db.Database.SqlQuery<Guid>($"""
            SELECT "InternalIdentityId" AS "Value"
            FROM organization_access.external_identity_bindings
            WHERE "Issuer" = {issuer} COLLATE "C" AND "Subject" = {subject} COLLATE "C"
            """).SingleOrDefaultAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        return identity == Guid.Empty ? null : new ClaimsPrincipal(new ClaimsIdentity(
            [new(ClaimTypes.NameIdentifier, identity.ToString("D")),
             new(IssuerClaim, issuer), new(SubjectClaim, subject)], authenticationType));
    }

    public static bool IsValidExternalIdentity(string issuer, string subject) =>
        issuer.Length is >= 9 and <= 2048
        && issuer.All(character => character is >= '!' and <= '~')
        && Uri.TryCreate(issuer, UriKind.Absolute, out var address)
        && address.Scheme == Uri.UriSchemeHttps
        && string.IsNullOrEmpty(address.UserInfo)
        && string.IsNullOrEmpty(address.Fragment)
        && string.IsNullOrEmpty(address.Query)
        && subject.Length is >= 1 and <= 255
        && subject.All(character => character is >= ' ' and <= '~');
}
