using System.Globalization;
using System.Security.Claims;
using Enginia360.Accounting.Contracts;
using Enginia360.Billing.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Enginia360.Accounting;

public static class AccountingModule
{
    private const string Receivable = "Receivable";
    private const string ServiceRevenue = "ServiceRevenue";
    private const string PartRevenue = "PartRevenue";
    private const string TaxPayable = "TaxPayable";

    public static IServiceCollection AddTechnicalAccounting(this IServiceCollection services, string connection)
    {
        services.AddDbContext<AccountingDbContext>(o => o.UseNpgsql(connection));
        return services;
    }

    public static WebApplication MapTechnicalAccounting(this WebApplication app)
    {
        var routes = app.MapGroup("/api/v1/accounting").RequireAuthorization()
            .AddEndpointFilter<AccountingTechnicalAuditFilter>();
        routes.MapPost("/invoice-journal-entries", Post);
        routes.MapGet("/invoice-journal-entries/{id:guid}", Read);
        return app;
    }

    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    private static string Text(decimal value) => value.ToString("0.000000", CultureInfo.InvariantCulture);
    private static decimal Number(string value) => decimal.Parse(value, CultureInfo.InvariantCulture);
    private static DateTimeOffset Now()
    {
        var now = DateTimeOffset.UtcNow;
        return new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
    }
    private static Task SetTenant(AccountingDbContext db, Guid tenant, CancellationToken ct) =>
        db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);

    private static async Task<IResult> Post(PostInvoiceJournalEntryRequest request, ClaimsPrincipal user,
        IAccountingAccess access, IConfirmedInvoices invoices, AccountingDbContext db, CancellationToken ct)
    {
        if (request.Id == Guid.Empty || request.InvoiceId == Guid.Empty || request.ChartVersion <= 0)
            return Results.BadRequest();
        var subject = Subject(user);
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        var invoice = await invoices.Find(member.TenantId, request.InvoiceId, ct);
        if (invoice is null) return Results.NotFound();
        if (await access.Authorize(subject, invoice.LegalEntityId, invoice.SiteId,
                "accounting.journal-entries.post", true, ct) is null)
            return Results.StatusCode(403);
        if (invoice.Currency != "EUR") return Results.Conflict(new { code = "journal_currency_unsupported" });

        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, member.TenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync(
            $"SELECT pg_advisory_xact_lock(hashtextextended({invoice.Id.ToString()}, 0))", ct);
        var replay = await db.Entries.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (replay is not null)
        {
            if (replay.InvoiceId != invoice.Id || replay.ChartVersion != request.ChartVersion)
                return Results.Conflict();
            await tx.CommitAsync(ct);
            return Results.Ok(await Contract(replay, member.TenantId, invoice, db, invoices, ct));
        }
        var posted = await db.Entries.AsNoTracking().SingleOrDefaultAsync(x => x.InvoiceId == invoice.Id, ct);
        if (posted is not null) return Results.Conflict(new { code = "invoice_already_posted" });

        var chart = await db.ChartAccounts.AsNoTracking().Where(x => x.TenantId == member.TenantId
            && x.LegalEntityId == invoice.LegalEntityId && x.Version == request.ChartVersion).ToListAsync(ct);
        var accounts = chart.ToDictionary(x => x.Purpose);
        if (!new[] { Receivable, ServiceRevenue, PartRevenue, TaxPayable }.All(accounts.ContainsKey))
            return Results.Conflict(new { code = "chart_of_accounts_incomplete" });

        var service = invoice.Summary.Lines.Where(x => x.Kind == "Service").Sum(x => Number(x.NetAmount));
        var part = invoice.Summary.Lines.Where(x => x.Kind == "Part").Sum(x => Number(x.NetAmount));
        var tax = Number(invoice.Summary.TaxAmount);
        var total = Number(invoice.Summary.Total);
        if (service + part != Number(invoice.Summary.NetAmount) || service + part + tax != total)
            return Results.Conflict(new { code = "invoice_values_inconsistent" });
        var candidates = new (string Purpose, decimal Debit, decimal Credit)[]
        {
            (Receivable, total, 0m), (ServiceRevenue, 0m, service), (PartRevenue, 0m, part), (TaxPayable, 0m, tax)
        };
        var lines = new List<JournalEntryLine>();
        foreach (var candidate in candidates.Where(x => x.Debit != 0m || x.Credit != 0m))
        {
            var account = accounts[candidate.Purpose];
            lines.Add(new JournalEntryLine
            {
                EntryId = request.Id, LineNumber = lines.Count + 1, TenantId = member.TenantId,
                AccountCode = account.AccountCode, AccountDescription = account.AccountDescription,
                Debit = candidate.Debit, Credit = candidate.Credit
            });
        }
        var debit = lines.Sum(x => x.Debit);
        var credit = lines.Sum(x => x.Credit);
        if (lines.Count < 2 || debit != credit)
            return Results.Conflict(new { code = "journal_entry_unbalanced" });
        var entry = new JournalEntry
        {
            Id = request.Id, TenantId = member.TenantId, InvoiceId = invoice.Id, OrderId = invoice.OrderId,
            LegalEntityId = invoice.LegalEntityId, SiteId = invoice.SiteId, ChartVersion = request.ChartVersion,
            EntryDate = invoice.DocumentDate, Currency = invoice.Currency, InvoiceReference = invoice.Reference,
            TotalDebit = debit, TotalCredit = credit, PostedAt = Now(), PostedBy = member.MembershipId
        };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO accounting.journal_entries ("Id","TenantId","InvoiceId","OrderId","LegalEntityId","SiteId",
              "ChartVersion","EntryDate","Currency","InvoiceReference","TotalDebit","TotalCredit","PostedAt","PostedBy")
            VALUES ({entry.Id},{entry.TenantId},{entry.InvoiceId},{entry.OrderId},{entry.LegalEntityId},{entry.SiteId},
              {entry.ChartVersion},{entry.EntryDate},{entry.Currency},{entry.InvoiceReference},{entry.TotalDebit},
              {entry.TotalCredit},{entry.PostedAt},{entry.PostedBy}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict();
        foreach (var line in lines)
            await db.Database.ExecuteSqlInterpolatedAsync($"""
                INSERT INTO accounting.journal_entry_lines ("EntryId","LineNumber","TenantId","AccountCode",
                  "AccountDescription","Debit","Credit")
                VALUES ({line.EntryId},{line.LineNumber},{line.TenantId},{line.AccountCode},{line.AccountDescription},
                  {line.Debit},{line.Credit})
                """, ct);
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/accounting/invoice-journal-entries/{entry.Id}",
            await Contract(entry, member.TenantId, invoice, db, invoices, ct));
    }

    private static async Task<IResult> Read(Guid id, ClaimsPrincipal user, IAccountingAccess access,
        IConfirmedInvoices invoices, AccountingDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        JournalEntry? entry;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, member.TenantId, ct);
            entry = await db.Entries.AsNoTracking()
                .SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
            await tx.CommitAsync(ct);
        }
        if (entry is null) return Results.NotFound();
        if (await access.Authorize(subject, entry.LegalEntityId, entry.SiteId,
                "accounting.journal-entries.read", false, ct) is null)
            return Results.NotFound();
        var invoice = await invoices.Find(member.TenantId, entry.InvoiceId, ct);
        if (invoice is null) return Results.Conflict(new { code = "invoice_source_missing" });
        return Results.Ok(await Contract(entry, member.TenantId, invoice, db, invoices, ct));
    }

    private static async Task<InvoiceJournalEntryContract> Contract(JournalEntry entry, Guid tenant,
        ConfirmedInvoiceSnapshot invoice, AccountingDbContext db, IConfirmedInvoices invoices, CancellationToken ct)
    {
        // The invoice link belongs to Billing: a failure there leaves a visible pending state, not a lost entry.
        Guid? linked;
        try
        {
            linked = invoice.JournalEntryId ?? await invoices.Link(tenant, entry.InvoiceId, entry.Id, ct);
        }
        catch (System.Data.Common.DbException)
        {
            linked = null;
        }
        List<JournalEntryLine> rows;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, tenant, ct);
            rows = await db.Lines.AsNoTracking().Where(x => x.EntryId == entry.Id)
                .OrderBy(x => x.LineNumber).ToListAsync(ct);
            await tx.CommitAsync(ct);
        }
        var debit = rows.Sum(x => x.Debit);
        var credit = rows.Sum(x => x.Credit);
        var state = linked is null ? "Pending" : linked == entry.Id ? "Linked" : "Conflict";
        return new(entry.Id, entry.InvoiceId, entry.OrderId, entry.LegalEntityId, entry.SiteId, entry.ChartVersion,
            entry.EntryDate, entry.Currency, entry.InvoiceReference,
            rows.Select(x => new JournalEntryLineContract(x.LineNumber, x.AccountCode, x.AccountDescription,
                Text(x.Debit), Text(x.Credit))).ToArray(),
            Text(debit), Text(credit), Text(debit - credit), debit == credit, state, entry.PostedAt);
    }
}

internal sealed class AccountingTechnicalAuditFilter(ILogger<AccountingTechnicalAuditFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var http = context.HttpContext;
        var action = http.Request.Method + " "
            + (http.GetEndpoint() as Microsoft.AspNetCore.Routing.RouteEndpoint)?.RoutePattern.RawText;
        Guid.TryParse(http.Request.RouteValues["id"]?.ToString(), out var resource);
        if (resource == Guid.Empty)
            resource = context.Arguments.OfType<PostInvoiceJournalEntryRequest>().Select(x => x.Id).FirstOrDefault();
        Guid.TryParse(http.User.FindFirstValue(ClaimTypes.NameIdentifier), out var identity);
        try
        {
            var result = await next(context);
            var status = (result as IStatusCodeHttpResult)?.StatusCode ?? 200;
            logger.LogInformation(new EventId(313), "Accounting audit {Action} {Outcome} {ResourceId} {IdentityId}",
                action, status, resource, identity);
            return result;
        }
        catch
        {
            logger.LogInformation(new EventId(313), "Accounting audit {Action} {Outcome} {ResourceId} {IdentityId}",
                action, 500, resource, identity);
            throw;
        }
    }
}
