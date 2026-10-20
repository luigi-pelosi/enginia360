using Microsoft.EntityFrameworkCore;

namespace Enginia360.Accounting;

internal sealed class AccountingDbContext(DbContextOptions<AccountingDbContext> options) : DbContext(options)
{
    internal DbSet<ChartAccount> ChartAccounts => Set<ChartAccount>();
    internal DbSet<JournalEntry> Entries => Set<JournalEntry>();
    internal DbSet<JournalEntryLine> Lines => Set<JournalEntryLine>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<ChartAccount>().ToTable("chart_accounts", "accounting")
            .HasKey(x => new { x.TenantId, x.LegalEntityId, x.Version, x.Purpose });
        b.Entity<JournalEntry>().ToTable("journal_entries", "accounting").HasKey(x => x.Id);
        b.Entity<JournalEntryLine>().ToTable("journal_entry_lines", "accounting")
            .HasKey(x => new { x.EntryId, x.LineNumber });
    }
}

internal sealed class ChartAccount
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public int Version { get; set; }
    public required string Purpose { get; set; }
    public required string AccountCode { get; set; }
    public required string AccountDescription { get; set; }
}

internal sealed class JournalEntry
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid InvoiceId { get; set; }
    public Guid OrderId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public int ChartVersion { get; set; }
    public DateOnly EntryDate { get; set; }
    public required string Currency { get; set; }
    public required string InvoiceReference { get; set; }
    public decimal TotalDebit { get; set; }
    public decimal TotalCredit { get; set; }
    public DateTimeOffset PostedAt { get; set; }
    public Guid PostedBy { get; set; }
}

internal sealed class JournalEntryLine
{
    public Guid EntryId { get; set; }
    public int LineNumber { get; set; }
    public Guid TenantId { get; set; }
    public required string AccountCode { get; set; }
    public required string AccountDescription { get; set; }
    public decimal Debit { get; set; }
    public decimal Credit { get; set; }
}
