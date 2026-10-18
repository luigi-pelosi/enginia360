namespace Enginia360.Counterparties.Domain;
internal sealed class Destination
{
    public Guid Id { get; init; }
    public Guid TenantId { get; init; }
    public Guid CounterpartyId { get; init; }
    public Guid OwnerLegalEntityId { get; init; }
    public required string Address { get; set; }
    public bool Published { get; set; }
}
