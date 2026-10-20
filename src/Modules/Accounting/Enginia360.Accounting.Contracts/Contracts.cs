using System.Text.Json.Serialization;

namespace Enginia360.Accounting.Contracts;

public sealed record AccountingGrant(Guid TenantId, Guid MembershipId);

public interface IAccountingAccess
{
    Task<AccountingGrant?> ResolveMembership(string subject, CancellationToken ct);
    Task<AccountingGrant?> Authorize(string subject, Guid legalEntityId, Guid siteId, string permission,
        bool requireCapability, CancellationToken ct);
}

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record PostInvoiceJournalEntryRequest(Guid Id, Guid InvoiceId, int ChartVersion);

public sealed record JournalEntryLineContract(int LineNumber, string AccountCode, string AccountDescription,
    string Debit, string Credit);

public sealed record InvoiceJournalEntryContract(Guid Id, Guid InvoiceId, Guid OrderId, Guid LegalEntityId,
    Guid SiteId, int ChartVersion, DateOnly EntryDate, string Currency, string InvoiceReference,
    IReadOnlyList<JournalEntryLineContract> Lines, string TotalDebit, string TotalCredit, string Difference,
    bool Balanced, string InvoiceLinkState, DateTimeOffset PostedAt);
