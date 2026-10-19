using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

internal sealed class WorkshopDbContext(DbContextOptions<WorkshopDbContext> options) : DbContext(options)
{
    internal DbSet<WorkOrder> Orders => Set<WorkOrder>();
    internal DbSet<DocumentTypeConfiguration> Configurations => Set<DocumentTypeConfiguration>();
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<WorkOrder>().ToTable("orders", "workshop").HasKey(x => x.Id);
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
