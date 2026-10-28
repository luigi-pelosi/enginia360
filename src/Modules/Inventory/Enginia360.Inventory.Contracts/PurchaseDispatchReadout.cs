using System.Text.Json.Nodes;

namespace Enginia360.Inventory.Contracts;

// Operator-facing derivation of one intent's dispatch state. Giobby's order status is never stock authority (D82); no host detail, vendor id or error text leaves this class.
public sealed record PurchaseDispatchView(string State, string? Reason, string? ExternalReference);

public static class PurchaseDispatchReadout
{
    // Bounded technical codes meaning "purchase setup missing or changed" (host configuration is never named).
    private static readonly HashSet<string> Configuration = ["mapping_missing", "provider_unconfigured", "destination_binding_mismatch", "identity_unverified"];

    public static PurchaseDispatchView From(bool priced, string? outcomeReference, PurchaseDelivery? delivery)
    {
        if (!priced) return new("not_sendable", "unpriced", null);
        if (outcomeReference is not null) return new("confirmed", null, outcomeReference);
        var reason = delivery?.LastError is { } error && Configuration.Contains(error) ? "configuration_missing" : null;
        // Completed without an Inventory outcome is the short window before the confirmation is recorded: still under verification.
        return delivery?.State is "Uncertain" or "Completed" ? new("uncertain", reason, null) : new("queued", reason, null);
    }

    // Replaces the internal outcome of every intent with the derived readout.
    public static void Apply(JsonObject state, IReadOnlyDictionary<Guid, PurchaseDelivery> deliveries)
    {
        if (state["intents"] is not JsonArray intents) return;
        foreach (var node in intents)
        {
            if (node is not JsonObject intent) continue;
            var priced = intent["acceptedPrice"] is not null;
            var reference = (intent["outcome"] as JsonObject)?["externalReference"]?.GetValue<string>();
            deliveries.TryGetValue(Guid.Parse(intent["id"]!.GetValue<string>()), out var delivery);
            var view = From(priced, reference, delivery);
            intent.Remove("outcome");
            intent["dispatch"] = new JsonObject { ["state"] = view.State, ["reason"] = view.Reason, ["externalReference"] = view.ExternalReference };
        }
    }
}
