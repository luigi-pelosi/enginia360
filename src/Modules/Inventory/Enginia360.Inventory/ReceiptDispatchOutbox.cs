using System.Text.Json;
using System.Text.RegularExpressions;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Inventory;

// Inventory owns intents, frozen prices and purchase outcomes. The dispatcher only receives frozen facts; Giobby stays the stock/document authority (D82).
internal sealed partial class ReceiptDispatchOutbox(InventoryDbContext db, IWorkshopAccess access) : IReceiptDispatchOutbox
{
    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$", RegexOptions.CultureInvariant)]
    private static partial Regex Reference();

    public async Task<IReadOnlyList<ReceiptOutboxEnvelope>> Pending(int limit, int offset, CancellationToken ct) =>
        await db.Database.SqlQuery<ReceiptOutboxEnvelope>($"""
            SELECT "TenantId", "LegalEntityId", "ReceiptId" FROM inventory.pending_receipt_dispatch({limit}, {offset})
            """).ToListAsync(ct);

    public async Task<ReceiptDispatchMessage?> Read(ReceiptOutboxEnvelope envelope, CancellationToken ct)
    {
        string? value;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {envelope.TenantId.ToString()}, true)", ct);
            value = await db.Database.SqlQuery<string?>($"SELECT inventory.read_receipt_dispatch({envelope.TenantId},{envelope.LegalEntityId},{envelope.ReceiptId})::text AS \"Value\"").SingleAsync(ct);
            await tx.CommitAsync(ct);
        }
        // Disabling a capability pauses new worker uses; history stays readable. The shared pool may have one slot, so this follows the commit.
        if (value is null || !await access.CapabilityEnabled(envelope.TenantId, envelope.LegalEntityId, "inventory", ct)
            || !await access.CapabilityEnabled(envelope.TenantId, envelope.LegalEntityId, "external-administration", ct)) return null;
        using var json = JsonDocument.Parse(value);
        var r = json.RootElement;
        string Text(string name) => r.GetProperty(name).GetString() ?? "";
        return new(r.GetProperty("tenantId").GetGuid(), r.GetProperty("legalEntityId").GetGuid(), r.GetProperty("siteId").GetGuid(), r.GetProperty("receiptId").GetGuid(),
            Guid.Parse(Text("catalogItemId")), Text("description"), Text("quantity"), Text("unitPrice"), Text("vendorId"), Text("vendorName"), Text("fingerprint"));
    }

    public async Task<bool> Record(ReceiptOutboxEnvelope envelope, string externalReference, CancellationToken ct)
    {
        if (!Reference().IsMatch(externalReference)) return false;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {envelope.TenantId.ToString()}, true)", ct);
        var result = await db.Database.SqlQuery<string>($"SELECT inventory.record_receipt_outcome({envelope.TenantId},{envelope.LegalEntityId},{envelope.ReceiptId},{externalReference}) AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return result is "recorded" or "replayed";
    }
}
