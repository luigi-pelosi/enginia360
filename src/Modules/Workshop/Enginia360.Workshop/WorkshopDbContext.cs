using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

internal sealed class WorkshopDbContext(DbContextOptions<WorkshopDbContext> options) : DbContext(options)
{
    internal DbSet<InstalledPart> Installations => Set<InstalledPart>();
    internal DbSet<WorkOrder> Orders => Set<WorkOrder>();
    internal DbSet<CarcassPolicy> CarcassPolicies => Set<CarcassPolicy>();
    internal DbSet<CommercialLine> Lines => Set<CommercialLine>();
    internal DbSet<LinePolicy> LinePolicies => Set<LinePolicy>();
    internal DbSet<WorkingGroup> WorkingGroups => Set<WorkingGroup>();
    internal DbSet<OrderNote> Notes => Set<OrderNote>();
    internal DbSet<EditorCommandReceipt> EditorCommands => Set<EditorCommandReceipt>();
    internal DbSet<DocumentTypeConfiguration> Configurations => Set<DocumentTypeConfiguration>();
    internal DbSet<TechnicalClosure> TechnicalClosures => Set<TechnicalClosure>();
    internal DbSet<AdministrativeDestination> AdministrativeDestinations => Set<AdministrativeDestination>();
    internal DbSet<AdministrativeRequest> AdministrativeRequests => Set<AdministrativeRequest>();
    internal DbSet<AdministrativeOutcomeRow> AdministrativeOutcomes => Set<AdministrativeOutcomeRow>();
    internal DbSet<AdministrativeClosure> AdministrativeClosures => Set<AdministrativeClosure>();
    internal DbSet<InternalBillingClaim> InternalBillingClaims => Set<InternalBillingClaim>();
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<TechnicalClosure>().ToTable("technical_closures", "workshop").HasKey(x => x.OrderId);
        b.Entity<AdministrativeDestination>().ToTable("administrative_destinations", "workshop").HasKey(x => new { x.TenantId, x.LegalEntityId, x.Version });
        b.Entity<AdministrativeRequest>().ToTable("administrative_requests", "workshop").HasKey(x => x.Id);
        b.Entity<AdministrativeRequest>().Property(x => x.Summary).HasColumnType("jsonb");
        b.Entity<AdministrativeRequest>().Property(x => x.NetAmount).HasPrecision(18, 6);
        b.Entity<AdministrativeRequest>().Property(x => x.TaxAmount).HasPrecision(18, 6);
        b.Entity<AdministrativeRequest>().Property(x => x.Total).HasPrecision(18, 6);
        b.Entity<AdministrativeOutcomeRow>().ToTable("administrative_outcomes", "workshop").HasKey(x => x.RequestId);
        b.Entity<AdministrativeClosure>().ToTable("administrative_closures", "workshop").HasKey(x => x.OrderId);
        b.Entity<InternalBillingClaim>().ToTable("internal_billing_claims", "workshop").HasKey(x => x.InvoiceId);
        b.Entity<InstalledPart>().ToTable("installations", "workshop").HasKey(x => x.Id);
        b.Entity<InstalledPart>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<CarcassPolicy>().ToTable("carcass_policies", "workshop")
            .HasKey(x => new { x.TenantId, x.LegalEntityId, x.DocumentTypeId, x.CatalogItemId, x.Version });
        b.Entity<WorkOrder>().ToTable("orders", "workshop").HasKey(x => x.Id);
        b.Entity<CommercialLine>().ToTable("commercial_lines", "workshop").HasKey(x => x.Id);
        b.Entity<CommercialLine>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<CommercialLine>().Property(x => x.UnitPrice).HasPrecision(12, 6);
        b.Entity<CommercialLine>().Property(x => x.DiscountPercent).HasPrecision(5, 2);
        b.Entity<CommercialLine>().Property(x => x.NetAmount).HasPrecision(18, 6);
        b.Entity<WorkingGroup>().ToTable("working_groups", "workshop").HasKey(x => x.Id);
        b.Entity<OrderNote>().ToTable("order_notes", "workshop").HasKey(x => x.Id);
        b.Entity<EditorCommandReceipt>().ToTable("editor_commands", "workshop").HasKey(x => x.CommandId);
        b.Entity<EditorCommandReceipt>().Property(x => x.Canonical).HasColumnType("jsonb");
        b.Entity<LinePolicy>().ToTable("line_policies", "workshop").HasKey(x => new { x.TenantId, x.LegalEntityId, x.DocumentTypeId, x.Version });
        b.Entity<DocumentTypeConfiguration>().ToTable("document_types", "workshop")
            .HasKey(x => new { x.TenantId, x.LegalEntityId, x.Id, x.Version });
    }
}
internal sealed class WorkOrder
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid DocumentTypeId { get; set; }
    public int ConfigurationVersion { get; set; }
    public Guid PayerId { get; set; }
    public Guid VehicleId { get; set; }
    public Guid VehicleHolderId { get; set; }
    public Guid CreatedByMembershipId { get; set; }
    // Persisted monotonic lifecycle version of the commercial content (never a count of rows).
    public int CommercialRevision { get; set; }
    internal OrderContract ToContract() => new(Id, LegalEntityId, SiteId, DocumentTypeId,
        ConfigurationVersion, PayerId, VehicleId, VehicleHolderId, true);
}
internal sealed class DocumentTypeConfiguration
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public int Version { get; set; }
    public required string Name { get; set; }
    public bool DirectCreationEnabled { get; set; }
}
internal sealed class CarcassPolicy
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid DocumentTypeId { get; set; }
    public Guid CatalogItemId { get; set; }
    public int Version { get; set; }
    public bool ReturnRequired { get; set; }
}
internal sealed class WorkingGroup
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public required string Title { get; set; }
    public required string State { get; set; }
    public int Version { get; set; }
    public int CreatedRevision { get; set; }
}
internal sealed class OrderNote
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public Guid WorkingGroupId { get; set; }
    public required string Description { get; set; }
    public required string State { get; set; }
    public int Version { get; set; }
    public int CreatedRevision { get; set; }
}
internal sealed class EditorCommandReceipt
{
    public Guid CommandId { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public required string Type { get; set; }
    public required string Canonical { get; set; }
    public Guid TargetId { get; set; }
    public int InitialRevision { get; set; }
    public int AppliedRevision { get; set; }
    public required string ResultKind { get; set; }
    public int? LinePolicyVersion { get; set; }
    public int StructurePolicyVersion { get; set; }
    internal WorkshopEditReceipt Receipt() => new(CommandId, OrderId, AppliedRevision, ResultKind, TargetId);
}
