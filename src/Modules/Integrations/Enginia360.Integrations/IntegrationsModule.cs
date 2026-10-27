using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Integrations;

// Host-selected external administrative anti-corruption adapter and durable dispatcher.
public static class IntegrationsModule
{
    // Host-owned, non-secret purchase destination descriptor; null unless the verified GiobbyV1 binding and scope are configured.
    public static string? PurchaseDestinationDescriptor(AdministrativeConnectorBinding binding, IConfiguration giobby) => PurchaseDestination.Descriptor(binding, giobby);

    public static IServiceCollection AddExternalAdministration(this IServiceCollection services, string connection, IConfiguration section)
    {
        var options = ConnectorOptions.From(section);
        services.AddSingleton(options);
        services.AddSingleton(options.Giobby!);
        services.AddSingleton(options.Binding);
        services.AddSingleton(options.Binding.Kind == "Unavailable" ? AdministrativeRuntime.Unavailable : new AdministrativeRuntime(options.Binding.Kind, 1));
        services.AddDbContext<IntegrationsDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<IAdministrativeDeliveries, AdministrativeDeliveries>();
        services.AddScoped<IAdministrativeRecovery, AdministrativeRecovery>();
        services.AddScoped<AdministrativeDispatcher>();
        services.AddHttpClient<SimulatorConnector>(client => { client.BaseAddress = options.BaseAddress; client.Timeout = options.Timeout; }).RemoveAllLoggers();
        services.AddHttpClient<GiobbySalesOrderConnector>((provider, client) => { client.BaseAddress = provider.GetRequiredService<GiobbyHost>().BaseAddress; client.Timeout = options.Timeout; })
            .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler { AllowAutoRedirect = false }).RemoveAllLoggers();
        services.AddScoped<IAdministrativeConnector>(p => (options.ProtocolVerified ? options.Kind : "Unavailable") switch
        {
            "GiobbyV1" => p.GetRequiredService<GiobbySalesOrderConnector>(), "SimulatorV1" => p.GetRequiredService<SimulatorConnector>(),
            _ => new UnavailableConnector()
        });
        services.AddHostedService<AdministrativeDispatchWorker>();
        return services;
    }
}

internal sealed record ConnectorOptions(Uri? BaseAddress, TimeSpan Timeout, TimeSpan PollInterval, TimeSpan RetryDelay, TimeSpan Lease)
{
    internal bool ProtocolVerified { get; init; } = true;
    internal string Kind { get; init; } = "SimulatorV1";
    internal GiobbyHost? Giobby { get; init; }
    internal AdministrativeConnectorBinding Binding => Kind == "GiobbyV1" && ProtocolVerified ? Giobby!.Binding : Kind == "SimulatorV1" && ProtocolVerified && BaseAddress is not null ? new("SimulatorV1", 1,
        Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes("SimulatorV1\n1\n" + BaseAddress.AbsoluteUri)))) : new("Unavailable", 0, "");

    internal static ConnectorOptions From(IConfiguration section)
    {
        // Host configuration only: tenants and payloads never choose the remote address.
        var configured = section["SimulatorBaseUrl"];
        Uri? uri = null;
        // Absent descriptor holds dependent dispatch without stopping core UI/history; a malformed one still fails startup.
        if (!string.IsNullOrEmpty(configured))
        {
            if (!Uri.TryCreate(configured, UriKind.Absolute, out uri) || uri.Scheme is not ("http" or "https")
                || uri.UserInfo.Length > 0 || uri.Query.Length > 0 || uri.Fragment.Length > 0 || !uri.AbsolutePath.EndsWith('/'))
                throw new InvalidOperationException("ExternalAdministration:SimulatorBaseUrl must be an absolute http(s) URL ending with '/'.");
        }
        var options = new ConnectorOptions(uri, Milliseconds(section, "TimeoutMilliseconds", 5000, 100, 60000),
            Milliseconds(section, "PollMilliseconds", 1000, 50, 60000), Milliseconds(section, "RetryMilliseconds", 2000, 50, 600000),
            Milliseconds(section, "LeaseMilliseconds", 30000, 1000, 600000));
        if (options.Lease <= options.Timeout * (section["Protocol"] == "GiobbyV1" ? 3 : 2)) throw new InvalidOperationException("ExternalAdministration lease must exceed the complete bounded HTTP sequence.");
        return options with { Kind = section["Protocol"] ?? "SimulatorV1", Giobby = new GiobbyHost(section.GetSection("Giobby")), ProtocolVerified = (section["Protocol"] is null or "SimulatorV1" or "GiobbyV1")
            && (section["ProtocolVersion"] is null or "1") };
    }
    private static TimeSpan Milliseconds(IConfiguration section, string key, int fallback, int min, int max)
    {
        var value = section.GetValue<int?>(key) ?? fallback;
        if (value < min || value > max) throw new InvalidOperationException($"ExternalAdministration:{key} must be between {min} and {max}.");
        return TimeSpan.FromMilliseconds(value);
    }
}
