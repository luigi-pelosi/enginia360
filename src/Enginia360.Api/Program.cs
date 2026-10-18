using Enginia360.Api.OrganizationAccess;
using Enginia360.Counterparties;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(options => options.IncludeScopes = true);
builder.Services.AddOpenApi();
builder.Services.AddOrganizationAccess(builder.Configuration);
if (builder.Configuration.GetValue<bool>("Counterparties:Enabled"))
{
    builder.Services.AddScoped<Enginia360.Counterparties.Contracts.ICounterpartyAccess, CounterpartyAccessAdapter>();
    builder.Services.AddCounterparties(builder.Configuration.GetConnectionString("OrganizationAccess")!);
}
var app = builder.Build();

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
            new Dictionary<string, object> { ["CorrelationId"] = correlationId }
        );
        await next(context);
        app.Logger.LogInformation(
            "HTTP {Method} completed with {StatusCode}",
            context.Request.Method,
            context.Response.StatusCode
        );
    }
);

app.UseAuthentication();
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
if (app.Configuration.GetValue<bool>("Counterparties:Enabled"))
    app.MapCounterparties();
app.MapOpenApi();
app.Run();

public sealed record BootstrapStatus(
    string Product,
    string Stage,
    bool FoundationDossierApproved,
    bool BusinessCapabilitiesAvailable
);

public partial class Program;
