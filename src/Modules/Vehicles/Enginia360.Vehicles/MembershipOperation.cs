using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using System.Security.Claims;

namespace Enginia360.Vehicles;

internal sealed partial class VehiclesDbContext
{
    internal async Task<IDbContextTransaction> BeginUserOperation(Guid? tenant, CancellationToken ct, System.Data.IsolationLevel isolation = System.Data.IsolationLevel.ReadCommitted)
    {
        // RepeatableRead fixes its snapshot at the FIRST SELECT (even set_config).
        // Wait on the SAME boundary before BEGIN, then hand it to the transaction.
        // No second key, weaker isolation, detached access read or worker fallback.
        var snapshotBoundary = isolation == System.Data.IsolationLevel.RepeatableRead;
        IDbContextTransaction? tx = null;
        if (snapshotBoundary) await Database.OpenConnectionAsync(ct);
        try
        {
            if (snapshotBoundary) await Database.ExecuteSqlRawAsync("SELECT pg_advisory_lock(777036)", ct);
            tx = await Database.BeginTransactionAsync(isolation, ct);
            if (snapshotBoundary) await Database.ExecuteSqlRawAsync("SELECT pg_advisory_xact_lock(777036)", ct);
            await Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant?.ToString("D") ?? ""}, true), set_config('app.legal_entity_id', {""}, true)", ct);
            if (configuration["Authentication:Profile"] == "SyntheticLegacy" && !configuration.GetValue<bool>("BrowserSessions:Enabled")) return tx;
            var principal = accessor.HttpContext?.User;
            var identity = principal?.FindFirstValue(ClaimTypes.NameIdentifier);
            var issuer = principal?.FindFirstValue("enginia360:verified-issuer");
            var subject = principal?.FindFirstValue("enginia360:external-subject");
            if (principal?.Identity?.IsAuthenticated != true || !Guid.TryParseExact(identity,"D",out var id) || id == Guid.Empty
                || string.IsNullOrEmpty(issuer) || string.IsNullOrEmpty(subject)) throw new UnauthorizedAccessException("Current verified identity required.");
            await Database.ExecuteSqlInterpolatedAsync($"""
                SELECT set_config('app.identity_subject', {id.ToString("D")}, true),
                  set_config('app.identity_issuer', {issuer}, true), set_config('app.external_subject', {subject}, true)
                """, ct);
            // 777036 plus exact binding/membership FOR SHARE remain owned by this
            // physical transaction until its data effect commits or rolls back.
            if (!await Database.SqlQuery<bool>($"SELECT organization_access.current_membership_access({tenant}::uuid) AS \"Value\"").SingleAsync(ct))
                throw new UnauthorizedAccessException("Current membership access required.");
            return tx;
        }
        catch
        {
            if (tx is not null) await tx.DisposeAsync();
            throw;
        }
        finally
        {
            if (snapshotBoundary)
            {
                try
                {
                    // Runs even after cancelled acquisition/refusal, never leave
                    // a session lock on a pooled physical connection.
                    await Database.ExecuteSqlRawAsync("SELECT pg_advisory_unlock(777036)", CancellationToken.None);
                }
                catch
                {
                    if (tx is not null) await tx.DisposeAsync();
                    Npgsql.NpgsqlConnection.ClearPool((Npgsql.NpgsqlConnection)Database.GetDbConnection());
                    throw;
                }
                finally { await Database.CloseConnectionAsync(); }
            }
        }
    }
}
