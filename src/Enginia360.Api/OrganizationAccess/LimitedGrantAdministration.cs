using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.OrganizationAccess;

public sealed record OperativeGrantCommand(Guid CommandId, Guid MandateId, Guid TargetMembershipId,
    Guid TenantId, Guid LegalEntityId, Guid SiteId, Guid WarehouseId, string? Action, string? Operation)
{
    public bool IsValid => CommandId != Guid.Empty && MandateId != Guid.Empty
        && TargetMembershipId != Guid.Empty && TenantId != Guid.Empty && LegalEntityId != Guid.Empty
        && SiteId != Guid.Empty && WarehouseId != Guid.Empty
        && Action is { Length: > 0 and <= 100 } && Operation is "grant" or "revoke";
}

public sealed record OperativeGrantOutcome(string Result);

public sealed partial class OrganizationContextService
{
    public async Task<string> GrantAdministration(string subject, CancellationToken c)
    {
        await using var tx = await db.Database.BeginTransactionAsync(c);
        await SetIdentity(subject, c);
        var result = await db.Database.SqlQuery<string>($"SELECT organization_access.grant_administration()::text AS \"Value\"").SingleAsync(c);
        await tx.CommitAsync(c);
        return result;
    }

    public async Task<string> CommandGrant(string subject, OperativeGrantCommand r, CancellationToken c)
    {
        await using var tx = await db.Database.BeginTransactionAsync(c);
        await SetIdentity(subject, c);
        var result = await db.Database.SqlQuery<string>($"SELECT organization_access.command_operative_grant({r.CommandId},{r.MandateId},{r.TargetMembershipId},{r.TenantId},{r.LegalEntityId},{r.SiteId},{r.WarehouseId},{r.Action},{r.Operation}) AS \"Value\"").SingleAsync(c);
        await tx.CommitAsync(c);
        return result;
    }
}
