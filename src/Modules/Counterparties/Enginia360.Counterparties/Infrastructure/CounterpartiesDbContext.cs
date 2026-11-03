using Enginia360.Counterparties.Domain;
using System.Security.Claims;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
namespace Enginia360.Counterparties.Infrastructure;
internal sealed class CounterpartiesDbContext(DbContextOptions<CounterpartiesDbContext> options,
    IHttpContextAccessor accessor, IConfiguration configuration) : DbContext(options)
{
    // Explicit owning-module boundary, not a SaveChanges/connection interceptor.
    // All current Counterparties runtime ports are user-derived (including the
    // Billing recipient lookup); none is accepted outbox/worker execution.
    internal async Task<IDbContextTransaction> BeginUserOperation(Guid tenant, Guid? company, CancellationToken ct)
    {
        var tx = await Database.BeginTransactionAsync(ct);
        try
        {
            await Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString("D")}, true), set_config('app.legal_entity_id', {company?.ToString("D") ?? ""}, true)", ct);
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
            if (!await Database.SqlQuery<bool>($"SELECT organization_access.current_membership_access({tenant}) AS \"Value\"").SingleAsync(ct))
                throw new UnauthorizedAccessException("Current membership access required.");
            return tx;
        }
        catch
        {
            await tx.DisposeAsync();
            throw;
        }
    }
    internal DbSet<Counterparty> Counterparties => Set<Counterparty>();
    internal DbSet<Destination> Destinations => Set<Destination>();
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Destination>().ToTable("destinations", "counterparties").HasKey(x => x.Id);
        b.Entity<Counterparty>().ToTable("counterparties", "counterparties").HasKey(x => x.Id);
    }
}
