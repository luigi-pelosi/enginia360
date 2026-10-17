using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.OrganizationAccess;

public sealed class OrganizationAccessDbContext(
    DbContextOptions<OrganizationAccessDbContext> options
) : DbContext(options)
{
    public DbSet<Tenant> Tenants => Set<Tenant>();
    public DbSet<LegalEntity> LegalEntities => Set<LegalEntity>();
    public DbSet<Site> Sites => Set<Site>();
    public DbSet<Warehouse> Warehouses => Set<Warehouse>();
    public DbSet<Membership> Memberships => Set<Membership>();
    public DbSet<MembershipScope> MembershipScopes => Set<MembershipScope>();
    public DbSet<CapabilityActivation> CapabilityActivations => Set<CapabilityActivation>();
    public DbSet<ContextNote> ContextNotes => Set<ContextNote>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.HasDefaultSchema("organization_access");
        b.Entity<Tenant>().ToTable("tenants").HasKey(x => x.Id);
        b.Entity<Tenant>().Property(x => x.Name).HasMaxLength(100);
        b.Entity<LegalEntity>().ToTable("legal_entities").HasKey(x => x.Id);
        b.Entity<LegalEntity>().HasAlternateKey(x => new { x.Id, x.TenantId });
        b.Entity<LegalEntity>().Property(x => x.Name).HasMaxLength(100);
        b.Entity<LegalEntity>().HasOne<Tenant>().WithMany().HasForeignKey(x => x.TenantId);
        b.Entity<Site>().ToTable("sites").HasKey(x => x.Id);
        b.Entity<Site>()
            .HasAlternateKey(x => new
            {
                x.Id,
                x.LegalEntityId,
                x.TenantId,
            });
        b.Entity<Site>().Property(x => x.Name).HasMaxLength(100);
        b.Entity<Site>()
            .HasOne<LegalEntity>()
            .WithMany()
            .HasForeignKey(x => new { x.LegalEntityId, x.TenantId })
            .HasPrincipalKey(x => new { x.Id, x.TenantId });
        b.Entity<Warehouse>().ToTable("warehouses").HasKey(x => x.Id);
        b.Entity<Warehouse>()
            .HasAlternateKey(x => new
            {
                x.Id,
                x.SiteId,
                x.LegalEntityId,
                x.TenantId,
            });
        b.Entity<Warehouse>().Property(x => x.Name).HasMaxLength(100);
        b.Entity<Warehouse>()
            .HasOne<Site>()
            .WithMany()
            .HasForeignKey(x => new
            {
                x.SiteId,
                x.LegalEntityId,
                x.TenantId,
            })
            .HasPrincipalKey(x => new
            {
                x.Id,
                x.LegalEntityId,
                x.TenantId,
            });
        b.Entity<Membership>().ToTable("memberships").HasKey(x => x.Id);
        b.Entity<Membership>().HasAlternateKey(x => new { x.Id, x.TenantId });
        b.Entity<Membership>().Property(x => x.IdentitySubject).HasMaxLength(200);
        b.Entity<Membership>().HasOne<Tenant>().WithMany().HasForeignKey(x => x.TenantId);
        b.Entity<Membership>().HasIndex(x => x.IdentitySubject).IsUnique();
        b.Entity<MembershipScope>().ToTable("membership_scopes").HasKey(x => x.Id);
        b.Entity<MembershipScope>().Property(x => x.Permission).HasMaxLength(100);
        b.Entity<MembershipScope>()
            .HasIndex(x => new
            {
                x.MembershipId,
                x.LegalEntityId,
                x.SiteId,
                x.WarehouseId,
                x.Permission,
            })
            .IsUnique();
        b.Entity<MembershipScope>()
            .HasOne<Membership>()
            .WithMany()
            .HasForeignKey(x => new { x.MembershipId, x.TenantId })
            .HasPrincipalKey(x => new { x.Id, x.TenantId });
        b.Entity<MembershipScope>()
            .HasOne<Warehouse>()
            .WithMany()
            .HasForeignKey(x => new
            {
                x.WarehouseId,
                x.SiteId,
                x.LegalEntityId,
                x.TenantId,
            })
            .HasPrincipalKey(x => new
            {
                x.Id,
                x.SiteId,
                x.LegalEntityId,
                x.TenantId,
            });
        b.Entity<CapabilityActivation>()
            .ToTable("capability_activations")
            .HasKey(x => new { x.LegalEntityId, x.Capability });
        b.Entity<CapabilityActivation>().Property(x => x.Capability).HasMaxLength(100);
        b.Entity<CapabilityActivation>()
            .HasOne<LegalEntity>()
            .WithMany()
            .HasForeignKey(x => x.LegalEntityId);
        b.Entity<ContextNote>()
            .ToTable(
                "context_notes",
                table =>
                    table.HasCheckConstraint(
                        "context_notes_Message_check",
                        "length(btrim(\"Message\")) BETWEEN 1 AND 200"
                    )
            )
            .HasKey(x => x.Id);
        b.Entity<ContextNote>().Property(x => x.Message).HasMaxLength(200);
        b.Entity<ContextNote>()
            .HasOne<Warehouse>()
            .WithMany()
            .HasForeignKey(x => new
            {
                x.WarehouseId,
                x.SiteId,
                x.LegalEntityId,
                x.TenantId,
            })
            .HasPrincipalKey(x => new
            {
                x.Id,
                x.SiteId,
                x.LegalEntityId,
                x.TenantId,
            });
    }
}

public sealed class Tenant
{
    public Guid Id { get; init; }
    public required string Name { get; init; }
}

public sealed class LegalEntity
{
    public Guid Id { get; init; }
    public Guid TenantId { get; init; }
    public required string Name { get; init; }
}

public sealed class Site
{
    public Guid Id { get; init; }
    public Guid LegalEntityId { get; init; }
    public Guid TenantId { get; init; }
    public required string Name { get; init; }
}

public sealed class Warehouse
{
    public Guid Id { get; init; }
    public Guid SiteId { get; init; }
    public Guid LegalEntityId { get; init; }
    public Guid TenantId { get; init; }
    public required string Name { get; init; }
}

public sealed class Membership
{
    public Guid Id { get; init; }
    public Guid TenantId { get; init; }
    public required string IdentitySubject { get; init; }
}

public sealed class MembershipScope
{
    public Guid Id { get; init; }
    public Guid MembershipId { get; init; }
    public Guid TenantId { get; init; }
    public Guid LegalEntityId { get; init; }
    public Guid SiteId { get; init; }
    public Guid WarehouseId { get; init; }
    public required string Permission { get; init; }
}

public sealed class CapabilityActivation
{
    public Guid LegalEntityId { get; init; }
    public required string Capability { get; init; }
    public bool Enabled { get; init; }
}

public sealed class ContextNote
{
    public Guid Id { get; init; }
    public Guid TenantId { get; init; }
    public Guid LegalEntityId { get; init; }
    public Guid SiteId { get; init; }
    public Guid WarehouseId { get; init; }
    public required string Message { get; init; }
}
