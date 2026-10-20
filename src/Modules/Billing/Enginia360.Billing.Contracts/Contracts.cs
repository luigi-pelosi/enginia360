using System.Text.Json.Serialization;

namespace Enginia360.Billing.Contracts;

public sealed record BillingGrant(Guid TenantId, Guid MembershipId);
public interface IBillingAccess
{
    Task<BillingGrant?> ResolveMembership(string subject, CancellationToken ct);
    Task<BillingGrant?> Authorize(string subject, Guid legalEntityId, Guid siteId, string permission, bool requireCapability, CancellationToken ct);
}
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record CreateWorkshopInvoiceRequest(Guid Id, Guid OrderId, Guid DocumentTypeId,
    int ConfigurationVersion, DateOnly DocumentDate, string Currency, string Reference);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record ConfirmInvoiceRequest(Guid Id, int ConfigurationVersion);
public sealed record InvoiceLineSnapshot(Guid Id, Guid OrderId, Guid CatalogItemId, int CatalogVersion,
    string CatalogLabel, string Kind, string Quantity, string UnitPrice, string DiscountPercent, string NetAmount,
    string TaxRate, Guid PayerId, Guid WorkingGroupId, int ConfigurationVersion);
public sealed record InvoiceSummarySnapshot(Guid OrderId, Guid PayerId, int Revision,
    IReadOnlyList<InvoiceLineSnapshot> Lines, string NetAmount, string TaxAmount, string Total, string Currency,
    string Policy);
public sealed record InvoicePartySnapshot(Guid Id, string LegalName, string FiscalIdentifier, string RegisteredOffice);
public sealed record TechnicalInvoiceContract(Guid Id, Guid OrderId, Guid LegalEntityId, Guid SiteId, Guid PayerId,
    Guid DocumentTypeId, int ConfigurationVersion, int DestinationVersion, int SourceRevision, DateOnly DocumentDate,
    string Currency, string Reference, InvoiceSummarySnapshot Summary, string Status,
    InvoicePartySnapshot? Issuer, InvoicePartySnapshot? Recipient,
    DateTimeOffset CreatedAt, DateTimeOffset? ConfirmedAt, Guid? JournalEntryId);
