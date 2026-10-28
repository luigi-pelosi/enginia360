using Enginia360.Inventory.Contracts;

namespace Enginia360.Integrations;

internal interface IPurchaseConnector
{
    Task<ConnectorResult> Submit(PurchaseDispatchMessage message, CancellationToken ct);
    Task<ConnectorResult> Status(PurchaseDispatchMessage message, CancellationToken ct);
}

internal sealed class UnavailablePurchaseConnector : IPurchaseConnector
{
    public Task<ConnectorResult> Submit(PurchaseDispatchMessage message, CancellationToken ct) => Task.FromResult(new ConnectorResult(ConnectorOutcome.Failure, Code: "provider_unconfigured"));
    public Task<ConnectorResult> Status(PurchaseDispatchMessage message, CancellationToken ct) => Submit(message, ct);
}
