using System.Diagnostics;
using System.Diagnostics.Metrics;
using Enginia360.Api.OrganizationAccess;
using Enginia360.Api.BrowserAuthentication;
using Enginia360.Counterparties;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(options => options.IncludeScopes = true);
if (builder.Configuration.GetValue<bool>("BrowserSessions:Enabled"))
    builder.Logging.AddFilter("Microsoft.AspNetCore.Hosting.Diagnostics", LogLevel.Warning);
builder.Services.AddOpenApi();
builder.Services.AddOrganizationAccess(builder.Configuration);
builder.Services.AddBrowserSessions(builder.Configuration);
if (builder.Configuration.GetValue<bool>("Counterparties:Enabled"))
{
    builder.Services.AddScoped<Enginia360.Counterparties.Contracts.ICounterpartyAccess, CounterpartyAccessAdapter>();
    builder.Services.AddCounterparties(builder.Configuration.GetConnectionString("OrganizationAccess")!);
}
if (builder.Configuration.GetValue<bool>("Workshop:Enabled"))
{
    if (!builder.Configuration.GetValue<bool>("Counterparties:Enabled"))
        throw new InvalidOperationException("Workshop requires Counterparties.");
    builder.Services.AddScoped<Enginia360.Workshop.Contracts.IWorkshopAccess, WorkshopAccessAdapter>();
    Enginia360.Catalog.CatalogModule.AddWorkshopCatalog(builder.Services, builder.Configuration.GetConnectionString("OrganizationAccess")!);
    Enginia360.Vehicles.VehiclesModule.AddWorkshopVehicles(builder.Services, builder.Configuration.GetConnectionString("OrganizationAccess")!);
    Enginia360.Workshop.WorkshopModule.AddWorkshop(builder.Services, builder.Configuration.GetConnectionString("OrganizationAccess")!);
}
if (builder.Configuration.GetValue<bool>("Inventory:Enabled"))
{
    if (!builder.Configuration.GetValue<bool>("Workshop:Enabled"))
        throw new InvalidOperationException("Inventory reservation requires Workshop.");
    builder.Services.AddScoped<Enginia360.Inventory.Contracts.IInventoryAccess, InventoryAccessAdapter>();
    Enginia360.Inventory.InventoryModule.AddInventory(builder.Services, builder.Configuration.GetConnectionString("OrganizationAccess")!);
}
var internalBilling = builder.Configuration.GetValue<bool>("InternalBilling:Enabled");
if (internalBilling)
{
    if (!builder.Configuration.GetValue<bool>("Workshop:Enabled"))
        throw new InvalidOperationException("Internal billing requires Workshop.");
    builder.Services.AddScoped<Enginia360.Billing.Contracts.IBillingAccess, BillingAccessAdapter>();
    Enginia360.Billing.BillingModule.AddInternalBilling(builder.Services,
        builder.Configuration.GetConnectionString("OrganizationAccess")!);
}
var technicalAccounting = builder.Configuration.GetValue<bool>("TechnicalAccounting:Enabled");
if (technicalAccounting)
{
    if (!internalBilling)
        throw new InvalidOperationException("Technical accounting requires internal billing.");
    builder.Services.AddScoped<Enginia360.Accounting.Contracts.IAccountingAccess, AccountingAccessAdapter>();
    Enginia360.Accounting.AccountingModule.AddTechnicalAccounting(builder.Services,
        builder.Configuration.GetConnectionString("OrganizationAccess")!);
}
var externalAdministration = builder.Configuration.GetValue<bool>("ExternalAdministration:Enabled");
if (externalAdministration)
{
    if (!builder.Configuration.GetValue<bool>("Inventory:Enabled"))
        throw new InvalidOperationException("External administration requires Workshop and Inventory.");
    Enginia360.Integrations.IntegrationsModule.AddExternalAdministration(builder.Services,
        builder.Configuration.GetConnectionString("OrganizationAccess")!, builder.Configuration.GetSection("ExternalAdministration"));
}
if (externalAdministration)
{
    // The browser never supplies a destination: it is frozen from the verified host binding at creation.
    builder.Services.AddSingleton(provider => Enginia360.Integrations.IntegrationsModule.PurchaseDestinationDescriptor(
        provider.GetRequiredService<Enginia360.Workshop.Contracts.AdministrativeConnectorBinding>(),
        builder.Configuration.GetSection("ExternalAdministration:Giobby")) is { } descriptor
        ? new Enginia360.Inventory.Contracts.PurchaseDestinationBinding(descriptor) : null!);
}
var app = builder.Build();
using var requestMeter = new Meter("Enginia360.Api", "1.0.0");
var requestDuration = requestMeter.CreateHistogram<double>("enginia360.http.duration", "s");

app.Use(
    async (context, next) =>
    {
        var values = context.Request.Headers["X-Correlation-ID"];
        var candidate = values.Count == 1 ? values[0] : null;
        var correlationId =
            candidate is { Length: > 0 and <= 64 }
            && candidate.All(character =>
                char.IsAsciiLetterOrDigit(character) || character is '-' or '_'
            )
                ? candidate
                : Guid.NewGuid().ToString("N");
        context.TraceIdentifier = correlationId;
        context.Response.Headers["X-Correlation-ID"] = correlationId;
        using var scope = app.Logger.BeginScope(
            new Dictionary<string, object>
            {
                ["CorrelationId"] = correlationId,
                ["TraceId"] = Activity.Current?.TraceId.ToString() ?? string.Empty,
                ["SpanId"] = Activity.Current?.SpanId.ToString() ?? string.Empty,
            }
        );
        var started = Stopwatch.GetTimestamp();
        try
        {
            await next(context);
        }
        finally
        {
            var statusCode = context.Response.StatusCode;
            var seconds = Stopwatch.GetElapsedTime(started).TotalSeconds;
            requestDuration.Record(seconds,
                new KeyValuePair<string, object?>("http.request.method", context.Request.Method),
                new KeyValuePair<string, object?>("http.response.status_code", statusCode));
            app.Logger.LogInformation(
                new EventId(314, "HttpDiagnostics"),
                "HTTP {Method} completed with {StatusCode} in {DurationSeconds} seconds",
                context.Request.Method, statusCode, seconds);
        }
    }
);

app.UseBrowserSessionTransport();
app.UseAuthentication();
app.UseBrowserSessionCsrf();
app.UseAuthorization();

app.MapGet(
        "/api/v1/system/status",
        () => new BootstrapStatus("Enginia360", "bootstrap", false, false)
    )
    .WithName("GetSystemStatus")
    .WithSummary(
        "Technical bootstrap only; no approved foundation dossier or business capabilities."
    );
app.MapHealthChecks(
    "/health/live",
    new Microsoft.AspNetCore.Diagnostics.HealthChecks.HealthCheckOptions { Predicate = _ => false }
);
app.MapHealthChecks(
    "/health/ready",
    new Microsoft.AspNetCore.Diagnostics.HealthChecks.HealthCheckOptions
    {
        Predicate = registration => !registration.Tags.Contains("external"),
    }
);
app.MapHealthChecks(
    "/health/dependencies",
    new Microsoft.AspNetCore.Diagnostics.HealthChecks.HealthCheckOptions
    {
        Predicate = registration => registration.Tags.Contains("external"),
    }
);
app.MapOrganizationAccess();
app.MapBrowserSessions();
if (app.Configuration.GetValue<bool>("Counterparties:Enabled"))
    app.MapCounterparties();
if (app.Configuration.GetValue<bool>("Workshop:Enabled"))
    Enginia360.Workshop.WorkshopModule.MapWorkshop(app, app.Configuration.GetValue<bool>("Inventory:Enabled"), externalAdministration,
        externalAdministration ? app.Services.GetRequiredService<Enginia360.Workshop.Contracts.AdministrativeRuntime>() : null);
if (app.Configuration.GetValue<bool>("Inventory:Enabled"))
    Enginia360.Inventory.InventoryModule.MapInventory(app);
if (internalBilling)
    Enginia360.Billing.BillingModule.MapInternalBilling(app);
if (technicalAccounting)
    Enginia360.Accounting.AccountingModule.MapTechnicalAccounting(app);
app.MapOpenApi();
app.Run();

public sealed record BootstrapStatus(
    string Product,
    string Stage,
    bool FoundationDossierApproved,
    bool BusinessCapabilitiesAvailable
);

public partial class Program;
