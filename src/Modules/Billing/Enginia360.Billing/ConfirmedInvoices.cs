using System.Text.Json;
using Enginia360.Billing.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Billing;

internal sealed class ConfirmedInvoices(BillingDbContext db) : IConfirmedInvoices
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public async Task<ConfirmedInvoiceSnapshot?> Find(Guid verifiedTenantId, Guid invoiceId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(verifiedTenantId, ct);
        var invoice = await db.Invoices.AsNoTracking()
            .SingleOrDefaultAsync(x => x.TenantId == verifiedTenantId && x.Id == invoiceId, ct);
        if (invoice is null) { await tx.CommitAsync(ct); return null; }
        var confirmed = await db.Confirmations.AsNoTracking().AnyAsync(x => x.InvoiceId == invoiceId, ct);
        var link = await db.JournalLinks.AsNoTracking().SingleOrDefaultAsync(x => x.InvoiceId == invoiceId, ct);
        await tx.CommitAsync(ct);
        if (!confirmed) return null;
        var summary = JsonSerializer.Deserialize<InvoiceSummarySnapshot>(invoice.Summary, Json)
            ?? throw new InvalidOperationException("Corrupt invoice summary snapshot.");
        return new(invoice.Id, invoice.TenantId, invoice.OrderId, invoice.LegalEntityId, invoice.SiteId,
            invoice.PayerId, invoice.DocumentDate, invoice.Currency, invoice.Reference, summary, link?.JournalEntryId);
    }

    public async Task<Guid?> Link(Guid verifiedTenantId, Guid invoiceId, Guid journalEntryId, CancellationToken ct)
    {
        if (journalEntryId == Guid.Empty) return null;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(verifiedTenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync(
            $"SELECT pg_advisory_xact_lock(hashtextextended({invoiceId.ToString()}, 0))", ct);
        var existing = await db.JournalLinks.AsNoTracking().SingleOrDefaultAsync(x => x.InvoiceId == invoiceId, ct);
        if (existing is not null) { await tx.CommitAsync(ct); return existing.JournalEntryId; }
        var now = DateTimeOffset.UtcNow;
        now = new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO billing.invoice_journal_links ("InvoiceId","TenantId","JournalEntryId","LinkedAt")
            VALUES ({invoiceId},{verifiedTenantId},{journalEntryId},{now}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0) return null;
        await tx.CommitAsync(ct);
        return journalEntryId;
    }

    private Task SetTenant(Guid tenant, CancellationToken ct) =>
        db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);
}
