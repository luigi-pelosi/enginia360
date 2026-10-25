using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Integrations;

// Connector for the simulated external administrative destination (anti-corruption layer + dispatcher).
public static class IntegrationsModule
{
    // Identity of the adapter registered by AddExternalAdministration: the synthetic protocol v1, not any real ERP.
    public static AdministrativeRuntime Runtime { get; } = new("SimulatorV1", 1);

    public static IServiceCollection AddExternalAdministration(this IServiceCollection services, string connection, IConfiguration section)
    {
        var options = ConnectorOptions.From(section);
        services.AddSingleton(options);
        services.AddSingleton(options.Binding);
        services.AddDbContext<IntegrationsDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<IAdministrativeDeliveries, AdministrativeDeliveries>();
        services.AddScoped<IAdministrativeRecovery, AdministrativeRecovery>();
        services.AddScoped<AdministrativeDispatcher>();
        services.AddHttpClient<SimulatorConnector>(client => { client.BaseAddress = options.BaseAddress; client.Timeout = options.Timeout; }).RemoveAllLoggers();
        services.AddHostedService<AdministrativeDispatchWorker>();
        return services;
    }
}

internal sealed record ConnectorOptions(Uri? BaseAddress, TimeSpan Timeout, TimeSpan PollInterval, TimeSpan RetryDelay, TimeSpan Lease)
{
    internal bool ProtocolVerified { get; init; } = true;
    internal AdministrativeConnectorBinding Binding => ProtocolVerified && BaseAddress is not null ? new("SimulatorV1", 1,
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
        if (options.Lease <= options.Timeout * 2) throw new InvalidOperationException("ExternalAdministration lease must exceed twice the timeout.");
        return options with { ProtocolVerified = (section["Protocol"] is null or "SimulatorV1")
            && (section["ProtocolVersion"] is null or "1") };
    }
    private static TimeSpan Milliseconds(IConfiguration section, string key, int fallback, int min, int max)
    {
        var value = section.GetValue<int?>(key) ?? fallback;
        if (value < min || value > max) throw new InvalidOperationException($"ExternalAdministration:{key} must be between {min} and {max}.");
        return TimeSpan.FromMilliseconds(value);
    }
}
