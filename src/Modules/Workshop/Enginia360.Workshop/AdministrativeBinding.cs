namespace Enginia360.Workshop;

// Owner-local append-only provenance; no URL, credential or mutable current-host reference.
internal sealed class AdministrativeBinding
{
    public Guid RequestId { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public int DestinationVersion { get; set; }
    public int ContractVersion { get; set; }
    public DateTimeOffset RequestedAt { get; set; }
    public Guid OperatorId { get; set; }
    public required string Kind { get; set; }
    public int ProtocolVersion { get; set; }
    public required string DestinationFingerprint { get; set; }
    internal Contracts.AdministrativeConnectorBinding Contract() => new(Kind, ProtocolVersion, DestinationFingerprint);
}
