namespace Enginia360.Counterparties.Domain;
internal sealed class Counterparty
{
    public Guid Id { get; init; }
    public Guid TenantId { get; init; }
    public required string LegalName { get; set; }
    public required string FiscalIdentifier { get; set; }
    public required string RegisteredOffice { get; set; }
}
