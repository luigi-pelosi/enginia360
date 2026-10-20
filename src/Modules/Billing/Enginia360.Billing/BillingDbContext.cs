using Microsoft.EntityFrameworkCore;

namespace Enginia360.Billing;

internal sealed class BillingDbContext(DbContextOptions<BillingDbContext> options) : DbContext(options)
{
    internal DbSet<BillingDocumentType> DocumentTypes => Set<BillingDocumentType>();
    internal DbSet<IssuerProfile> IssuerProfiles => Set<IssuerProfile>();
    internal DbSet<TechnicalInvoice> Invoices => Set<TechnicalInvoice>();
    internal DbSet<InvoiceConfirmation> Confirmations => Set<InvoiceConfirmation>();
    internal DbSet<InvoiceJournalLink> JournalLinks => Set<InvoiceJournalLink>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<BillingDocumentType>().ToTable("document_types", "billing")
            .HasKey(x => new { x.TenantId, x.LegalEntityId, x.Id, x.Version });
        b.Entity<IssuerProfile>().ToTable("issuer_profiles", "billing")
            .HasKey(x => new { x.TenantId, x.LegalEntityId, x.Version });
        b.Entity<TechnicalInvoice>().ToTable("invoices", "billing").HasKey(x => x.Id);
        b.Entity<TechnicalInvoice>().Property(x => x.Summary).HasColumnType("jsonb");
        b.Entity<InvoiceConfirmation>().ToTable("invoice_confirmations", "billing").HasKey(x => x.InvoiceId);
        b.Entity<InvoiceConfirmation>().Property(x => x.Issuer).HasColumnType("jsonb");
        b.Entity<InvoiceConfirmation>().Property(x => x.Recipient).HasColumnType("jsonb");
        b.Entity<InvoiceJournalLink>().ToTable("invoice_journal_links", "billing").HasKey(x => x.InvoiceId);
    }
}

internal sealed class BillingDocumentType
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid Id { get; set; }
    public int Version { get; set; }
    public required string Code { get; set; }
    public bool WorkshopSourceAllowed { get; set; }
    public bool ConfirmationAllowed { get; set; }
}
internal sealed class IssuerProfile
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public int Version { get; set; }
    public required string LegalName { get; set; }
    public required string FiscalIdentifier { get; set; }
    public required string RegisteredOffice { get; set; }
}
internal sealed class TechnicalInvoice
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid PayerId { get; set; }
    public Guid DocumentTypeId { get; set; }
    public int ConfigurationVersion { get; set; }
    public int DestinationVersion { get; set; }
    public int SourceRevision { get; set; }
    public DateOnly DocumentDate { get; set; }
    public required string Currency { get; set; }
    public required string Reference { get; set; }
    public required string Summary { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public Guid CreatedBy { get; set; }
}
internal sealed class InvoiceConfirmation
{
    public Guid InvoiceId { get; set; }
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public int ConfigurationVersion { get; set; }
    public required string Issuer { get; set; }
    public required string Recipient { get; set; }
    public DateTimeOffset ConfirmedAt { get; set; }
    public Guid ConfirmedBy { get; set; }
}
internal sealed class InvoiceJournalLink
{
    public Guid InvoiceId { get; set; }
    public Guid TenantId { get; set; }
    public Guid JournalEntryId { get; set; }
    public DateTimeOffset LinkedAt { get; set; }
}
