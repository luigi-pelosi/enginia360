using System.Globalization;
using System.Security.Claims;
using System.Text.Json;
using System.Text.RegularExpressions;
using Enginia360.Billing.Contracts;
using Enginia360.Counterparties.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Enginia360.Billing;

public static partial class BillingModule
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public static IServiceCollection AddInternalBilling(this IServiceCollection services, string connection)
    {
        services.AddDbContext<BillingDbContext>(o => o.UseNpgsql(connection));
        return services;
    }

    public static WebApplication MapInternalBilling(this WebApplication app)
    {
        var routes = app.MapGroup("/api/v1/billing").RequireAuthorization().AddEndpointFilter<BillingTechnicalAuditFilter>();
        routes.MapPost("/workshop-invoices", Create);
        routes.MapGet("/workshop-invoices/{id:guid}", Read);
        routes.MapPost("/workshop-invoices/{id:guid}/confirmation", Confirm);
        return app;
    }

    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9/.-]{0,63}$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex Reference();
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    private static DateTimeOffset Now()
    {
        var now = DateTimeOffset.UtcNow;
        return new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
    }
    private static Task SetTenant(BillingDbContext db, Guid tenant, CancellationToken ct) =>
        db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);

    private static async Task<IResult> Create(CreateWorkshopInvoiceRequest request, ClaimsPrincipal user,
        IBillingAccess access, IWorkshopBillingSources sources, BillingDbContext db, CancellationToken ct)
    {
        if (request.Id == Guid.Empty || request.OrderId == Guid.Empty || request.DocumentTypeId == Guid.Empty
            || request.ConfigurationVersion <= 0 || request.DocumentDate == default || request.Currency != "EUR"
            || request.Reference is null || !Reference().IsMatch(request.Reference))
            return Results.BadRequest();
        var subject = Subject(user);
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        var candidate = await sources.Find(member.TenantId, request.OrderId, ct);
        if (candidate is null) return Results.NotFound();
        if (await access.Authorize(subject, candidate.LegalEntityId, candidate.SiteId, "billing.invoices.create", true, ct) is null)
            return Results.StatusCode(403);
        await using (var configurationTx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, member.TenantId, ct);
            var configuration = await db.DocumentTypes.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId
                && x.LegalEntityId == candidate.LegalEntityId && x.Id == request.DocumentTypeId
                && x.Version == request.ConfigurationVersion, ct);
            if (configuration is not { WorkshopSourceAllowed: true }) return Results.Conflict(new { code = "invoice_workflow_not_allowed" });
            await configurationTx.CommitAsync(ct);
        }
        var source = await sources.Allocate(member.TenantId, request.OrderId, request.Id, candidate.Revision, ct);
        if (source is null) return Results.Conflict(new { code = "administrative_destination_conflict" });
        var summary = Snapshot(source.Summary);
        var row = new TechnicalInvoice
        {
            Id = request.Id, TenantId = member.TenantId, OrderId = source.OrderId, LegalEntityId = source.LegalEntityId,
            SiteId = source.SiteId, PayerId = source.PayerId, DocumentTypeId = request.DocumentTypeId,
            ConfigurationVersion = request.ConfigurationVersion, DestinationVersion = source.DestinationVersion,
            SourceRevision = source.Revision, DocumentDate = request.DocumentDate, Currency = request.Currency,
            Reference = request.Reference, Summary = JsonSerializer.Serialize(summary, Json), CreatedAt = Now(),
            CreatedBy = member.MembershipId
        };
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, member.TenantId, ct);
        var existing = await db.Invoices.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (existing is not null)
        {
            if (!Same(existing, row)) return Results.Conflict();
            await tx.CommitAsync(ct);
            return Results.Ok(await Contract(existing, member.TenantId, db, ct));
        }
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO billing.invoices ("Id","TenantId","OrderId","LegalEntityId","SiteId","PayerId","DocumentTypeId",
              "ConfigurationVersion","DestinationVersion","SourceRevision","DocumentDate","Currency","Reference","Summary","CreatedAt","CreatedBy")
            VALUES ({row.Id},{row.TenantId},{row.OrderId},{row.LegalEntityId},{row.SiteId},{row.PayerId},{row.DocumentTypeId},
              {row.ConfigurationVersion},{row.DestinationVersion},{row.SourceRevision},{row.DocumentDate},{row.Currency},{row.Reference},
              CAST({row.Summary} AS jsonb),{row.CreatedAt},{row.CreatedBy}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0)
        {
            var concurrent = await db.Invoices.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
            if (concurrent is null || !Same(concurrent, row)) return Results.Conflict();
            await tx.CommitAsync(ct);
            return Results.Ok(await Contract(concurrent, member.TenantId, db, ct));
        }
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/billing/workshop-invoices/{row.Id}", await Contract(row, member.TenantId, db, ct));
    }

    private static async Task<IResult> Read(Guid id, ClaimsPrincipal user, IBillingAccess access,
        BillingDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        TechnicalInvoice? row;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, member.TenantId, ct);
            row = await db.Invoices.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
            await tx.CommitAsync(ct);
        }
        if (row is null || await access.Authorize(subject, row.LegalEntityId, row.SiteId, "billing.invoices.read", false, ct) is null)
            return Results.NotFound();
        return Results.Ok(await Contract(row, member.TenantId, db, ct));
    }

    private static async Task<IResult> Confirm(Guid id, ConfirmInvoiceRequest request, ClaimsPrincipal user,
        IBillingAccess access, IInvoiceCounterparties counterparties, BillingDbContext db, CancellationToken ct)
    {
        if (id == Guid.Empty || request.Id == Guid.Empty || request.ConfigurationVersion <= 0) return Results.BadRequest();
        var subject = Subject(user);
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        TechnicalInvoice? invoice;
        await using (var readTx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, member.TenantId, ct);
            invoice = await db.Invoices.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
            await readTx.CommitAsync(ct);
        }
        if (invoice is null) return Results.NotFound();
        if (await access.Authorize(subject, invoice.LegalEntityId, invoice.SiteId, "billing.invoices.confirm", true, ct) is null)
            return Results.StatusCode(403);
        if (request.ConfigurationVersion != invoice.ConfigurationVersion)
            return Results.Conflict(new { code = "invoice_configuration_changed" });
        var recipient = await counterparties.Find(member.TenantId, invoice.PayerId, ct);
        if (recipient is null) return Results.Conflict(new { code = "invoice_recipient_missing" });
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, member.TenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({id.ToString()}, 0))", ct);
        var replay = await db.Confirmations.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (replay is not null)
        {
            if (replay.InvoiceId != id || replay.ConfigurationVersion != request.ConfigurationVersion) return Results.Conflict();
            await tx.CommitAsync(ct);
            return Results.Ok(await Contract(invoice, member.TenantId, db, ct));
        }
        if (await db.Confirmations.AnyAsync(x => x.InvoiceId == id, ct))
            return Results.Conflict(new { code = "invoice_already_confirmed" });
        var configuration = await db.DocumentTypes.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId
            && x.LegalEntityId == invoice.LegalEntityId && x.Id == invoice.DocumentTypeId
            && x.Version == request.ConfigurationVersion, ct);
        var issuer = await db.IssuerProfiles.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId
            && x.LegalEntityId == invoice.LegalEntityId && x.Version == request.ConfigurationVersion, ct);
        if (configuration is not { ConfirmationAllowed: true } || issuer is null)
            return Results.Conflict(new { code = "invoice_confirmation_not_allowed" });
        var issuerSnapshot = new InvoicePartySnapshot(invoice.LegalEntityId, issuer.LegalName, issuer.FiscalIdentifier, issuer.RegisteredOffice);
        var recipientSnapshot = new InvoicePartySnapshot(recipient.Id, recipient.LegalName, recipient.FiscalIdentifier, recipient.RegisteredOffice);
        var confirmation = new InvoiceConfirmation { InvoiceId = id, Id = request.Id, TenantId = member.TenantId,
            ConfigurationVersion = request.ConfigurationVersion, Issuer = JsonSerializer.Serialize(issuerSnapshot, Json),
            Recipient = JsonSerializer.Serialize(recipientSnapshot, Json), ConfirmedAt = Now(), ConfirmedBy = member.MembershipId };
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO billing.invoice_confirmations ("InvoiceId","Id","TenantId","ConfigurationVersion","Issuer","Recipient","ConfirmedAt","ConfirmedBy")
            VALUES ({confirmation.InvoiceId},{confirmation.Id},{confirmation.TenantId},{confirmation.ConfigurationVersion},
              CAST({confirmation.Issuer} AS jsonb),CAST({confirmation.Recipient} AS jsonb),{confirmation.ConfirmedAt},{confirmation.ConfirmedBy})
            """, ct);
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/billing/workshop-invoices/{id}", await Contract(invoice, member.TenantId, db, ct));
    }

    private static bool Same(TechnicalInvoice x, TechnicalInvoice y) => x.OrderId == y.OrderId
        && x.DocumentTypeId == y.DocumentTypeId && x.ConfigurationVersion == y.ConfigurationVersion
        && x.DocumentDate == y.DocumentDate && x.Currency == y.Currency && x.Reference == y.Reference;

    private static InvoiceSummarySnapshot Snapshot(CommercialSummary source) => new(source.OrderId, source.PayerId,
        source.Revision, source.Lines.Select(x => new InvoiceLineSnapshot(x.Id, x.OrderId, x.CatalogItemId, x.CatalogVersion,
            x.CatalogLabel, x.Kind, x.Quantity, x.UnitPrice, x.DiscountPercent, x.NetAmount, x.TaxRate, x.PayerId,
            x.WorkingGroupId, x.ConfigurationVersion)).ToArray(),
        source.NetAmount, source.TaxAmount, source.Total, source.Currency, source.Policy);

    private static async Task<TechnicalInvoiceContract> Contract(TechnicalInvoice row, Guid tenant,
        BillingDbContext db, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, tenant, ct);
        var confirmation = await db.Confirmations.AsNoTracking().SingleOrDefaultAsync(x => x.InvoiceId == row.Id, ct);
        var link = await db.JournalLinks.AsNoTracking().SingleOrDefaultAsync(x => x.InvoiceId == row.Id, ct);
        await tx.CommitAsync(ct);
        var summary = JsonSerializer.Deserialize<InvoiceSummarySnapshot>(row.Summary, Json)
            ?? throw new InvalidOperationException("Corrupt invoice summary snapshot.");
        var issuer = confirmation is null ? null : JsonSerializer.Deserialize<InvoicePartySnapshot>(confirmation.Issuer, Json);
        var recipient = confirmation is null ? null : JsonSerializer.Deserialize<InvoicePartySnapshot>(confirmation.Recipient, Json);
        return new(row.Id, row.OrderId, row.LegalEntityId, row.SiteId, row.PayerId, row.DocumentTypeId,
            row.ConfigurationVersion, row.DestinationVersion, row.SourceRevision, row.DocumentDate, row.Currency,
            row.Reference, summary, confirmation is null ? "Draft" : "Confirmed", issuer, recipient, row.CreatedAt,
            confirmation?.ConfirmedAt, link?.JournalEntryId);
    }
}

internal sealed class BillingTechnicalAuditFilter(ILogger<BillingTechnicalAuditFilter> logger) : IEndpointFilter
{
    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        var http = context.HttpContext;
        var action = http.Request.Method + " " + (http.GetEndpoint() as Microsoft.AspNetCore.Routing.RouteEndpoint)?.RoutePattern.RawText;
        Guid.TryParse(http.Request.RouteValues["id"]?.ToString(), out var resource);
        if (resource == Guid.Empty)
            resource = context.Arguments.OfType<CreateWorkshopInvoiceRequest>().Select(x => x.Id).FirstOrDefault();
        Guid.TryParse(http.User.FindFirstValue(ClaimTypes.NameIdentifier), out var identity);
        try
        {
            var result = await next(context);
            var status = (result as IStatusCodeHttpResult)?.StatusCode ?? 200;
            logger.LogInformation(new EventId(312), "Billing audit {Action} {Outcome} {ResourceId} {IdentityId}", action, status, resource, identity);
            return result;
        }
        catch
        {
            logger.LogInformation(new EventId(312), "Billing audit {Action} {Outcome} {ResourceId} {IdentityId}", action, 500, resource, identity);
            throw;
        }
    }
}
