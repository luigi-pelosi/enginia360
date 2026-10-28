using System.Text.Json;
using System.Text.RegularExpressions;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Inventory;

// Inventory owns intents, frozen prices and purchase outcomes. The dispatcher only receives frozen facts; Giobby stays the stock/document authority (D82).
internal sealed partial class PurchaseDispatchOutbox(InventoryDbContext db, IWorkshopAccess access) : IPurchaseDispatchOutbox
{
    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$", RegexOptions.CultureInvariant)]
    private static partial Regex Reference();

    public async Task<IReadOnlyList<PurchaseOutboxEnvelope>> Pending(int limit, int offset, CancellationToken ct) =>
        await db.Database.SqlQuery<PurchaseOutboxEnvelope>($"""
            SELECT "TenantId", "LegalEntityId", "IntentId" FROM inventory.pending_purchase_dispatch({limit}, {offset})
            """).ToListAsync(ct);

    public async Task<PurchaseDispatchMessage?> Read(PurchaseOutboxEnvelope envelope, CancellationToken ct)
    {
        string? value;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {envelope.TenantId.ToString()}, true)", ct);
            value = await db.Database.SqlQuery<string?>($"SELECT inventory.read_purchase_dispatch({envelope.TenantId},{envelope.LegalEntityId},{envelope.IntentId})::text AS \"Value\"").SingleAsync(ct);
            await tx.CommitAsync(ct);
        }
        // Disabling a capability pauses new worker uses; history stays readable. The shared pool may have one slot, so this follows the commit.
        if (value is null || !await access.CapabilityEnabled(envelope.TenantId, envelope.LegalEntityId, "inventory", ct)
            || !await access.CapabilityEnabled(envelope.TenantId, envelope.LegalEntityId, "external-administration", ct)) return null;
        using var json = JsonDocument.Parse(value);
        var r = json.RootElement;
        string Text(string name) => r.GetProperty(name).GetString() ?? "";
        return new(r.GetProperty("tenantId").GetGuid(), r.GetProperty("legalEntityId").GetGuid(), r.GetProperty("siteId").GetGuid(), r.GetProperty("intentId").GetGuid(),
            Guid.Parse(Text("catalogItemId")), Text("description"), Text("quantity"), Text("unitPrice"), Text("vendorId"), Text("vendorName"), Text("fingerprint"));
    }

    public async Task<bool> Record(PurchaseOutboxEnvelope envelope, PurchaseOutcome outcome, CancellationToken ct)
    {
        if (outcome is not { Status: "Confirmed", RejectionCode: null, ExternalReference: { } reference } || !Reference().IsMatch(reference)) return false;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {envelope.TenantId.ToString()}, true)", ct);
        var result = await db.Database.SqlQuery<string>($"SELECT inventory.record_purchase_outcome({envelope.TenantId},{envelope.LegalEntityId},{envelope.IntentId},{reference}) AS \"Value\"").SingleAsync(ct);
        await tx.CommitAsync(ct);
        return result is "recorded" or "replayed";
    }
}
