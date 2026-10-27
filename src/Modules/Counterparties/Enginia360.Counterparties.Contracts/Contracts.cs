namespace Enginia360.Counterparties.Contracts;

public sealed record CounterpartyContract(Guid Id, Guid TenantId, string LegalName, string FiscalIdentifier, string RegisteredOffice);
public sealed record UpdateCounterpartyRequest(Guid LegalEntityId, string? LegalName, string? FiscalIdentifier, string? RegisteredOffice, Guid? CommandId = null, int? AuthorityVersion = null, int? ExpectedRevision = null);
public sealed record SupplierRoleRequest(Guid LegalEntityId, bool? IsSupplier, Guid? CommandId = null, int? AuthorityVersion = null, int? ExpectedRevision = null);
public sealed record CompanyRequest(Guid LegalEntityId);
public sealed record DestinationRequest(Guid LegalEntityId, string? Address);
public sealed record DestinationContract(Guid Id, Guid CounterpartyId, Guid OwnerLegalEntityId, string Address, bool Published);
public sealed record CounterpartyAccess(Guid TenantId, Guid MembershipId);
// Host adapter resolves verified membership and resource permissions; no ORM crosses this port.
public sealed record CounterpartyCompany(Guid LegalEntityId, string LegalEntityName);
public interface IWorkshopCounterparties
{
    Task<bool> CanUsePayer(string subject, Guid verifiedTenantId, Guid companyId, Guid counterpartyId, CancellationToken ct);
}
public sealed record InvoiceCounterparty(Guid Id, string LegalName, string FiscalIdentifier, string RegisteredOffice);
public interface IInvoiceCounterparties
{
    Task<InvoiceCounterparty?> Find(Guid verifiedTenantId, Guid counterpartyId, CancellationToken ct);
}
public interface ICounterpartyAccess
{
    Task<IReadOnlyList<CounterpartyCompany>> ListCompanies(string subject, CancellationToken cancellationToken);
    Task<CounterpartyAccess?> Authorize(string subject, Guid legalEntityId, string permission, CancellationToken cancellationToken);
}
