using System.Text.Json.Serialization;

namespace Enginia360.Workshop.Contracts;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow), JsonNumberHandling(JsonNumberHandling.Strict)]
public sealed record TechnicalClosureRequest(Guid Id, int ExpectedRevision);
public sealed record TechnicalClosureContract(Guid Id, Guid OrderId, int Revision, DateTimeOffset ClosedAt, Guid OperatorId);

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow), JsonNumberHandling(JsonNumberHandling.Strict)]
public sealed record AdministrativeRequestCommand(Guid Id, int ExpectedRevision);
// Connector-owned transport state. Never a business outcome by itself (D40).
public sealed record AdministrativeDelivery(string State, int Attempts, DateTimeOffset? LastAttemptAt, DateTimeOffset? NextAttemptAt, string? LastError, int Failures = 0);
// Immutable owner-local request with its q6 commercial snapshot; Status changes once, only from a business outcome.
public sealed record AdministrativeRequestContract(Guid Id, Guid OrderId, Guid LegalEntityId, Guid SiteId,
    string Destination, int DestinationVersion, int ContractVersion, CommercialSummary Summary, DateTimeOffset RequestedAt,
    Guid OperatorId, string Status, string? ExternalReference, string? RejectionCode, DateTimeOffset? OutcomeAt, AdministrativeDelivery Delivery,
    AdministrativeConnectorBinding? ConnectorBinding = null);

// Server composition supplies this immutable technical descriptor, never an address or credential.
// It identifies only the existing synthetic protocol, not a qualified Giobby business identity.
public sealed record AdministrativeConnectorBinding(string Kind, int ProtocolVersion, string DestinationFingerprint);

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record AdministrativeClosureCommand(Guid Id);
public sealed record AdministrativeClosureContract(Guid Id, Guid OrderId, Guid RequestId, string ExternalReference, DateTimeOffset ClosedAt, Guid OperatorId);
public sealed record OrderClosureState(Guid OrderId, string Status, TechnicalClosureContract? TechnicalClosure,
    AdministrativeRequestContract? Request, AdministrativeClosureContract? AdministrativeClosure);

// Server-owned envelope from the Workshop outbox: the only source of a dispatcher's tenant context.
public sealed record AdministrativeOutboxEnvelope(Guid TenantId, Guid RequestId);
public sealed record AdministrativeDispatchMessage(Guid TenantId, Guid RequestId, Guid OrderId, Guid LegalEntityId, Guid SiteId,
    int ContractVersion, CommercialSummary Summary, AdministrativeConnectorBinding? ConnectorBinding = null);
public sealed record AdministrativeOutcome(string Status, string? ExternalReference, string? RejectionCode);
// Implemented by Workshop, owner of requests and outcome consequences; used by the connector worker.
public interface IWorkshopAdministrativeOutbox
{
    Task<IReadOnlyList<AdministrativeOutboxEnvelope>> Pending(int limit, int offset, CancellationToken ct);
    Task<AdministrativeDispatchMessage?> Read(AdministrativeOutboxEnvelope envelope, CancellationToken ct);
    // Insert-only and idempotent: an identical outcome is accepted again, a different one is refused.
    Task<bool> Record(AdministrativeOutboxEnvelope envelope, AdministrativeOutcome outcome, CancellationToken ct);
}
// Implemented by the connector, owner of delivery attempts.
public sealed record AdministrativeReconciliation(bool Replayed);
public interface IAdministrativeRecovery
{
    Task<AdministrativeReconciliation?> Reconcile(Guid verifiedTenantId, Guid requestId, Guid commandId, Guid operatorId, CancellationToken ct);
}

public interface IAdministrativeDeliveries
{
    Task<IReadOnlyDictionary<Guid, AdministrativeDelivery>> Read(Guid verifiedTenantId, IReadOnlyCollection<Guid> requestIds, CancellationToken ct);
}
