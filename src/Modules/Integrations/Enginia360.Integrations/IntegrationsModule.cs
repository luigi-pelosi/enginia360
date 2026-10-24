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
        services.AddDbContext<IntegrationsDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<IAdministrativeDeliveries, AdministrativeDeliveries>();
        services.AddScoped<IAdministrativeRecovery, AdministrativeRecovery>();
        services.AddScoped<AdministrativeDispatcher>();
        services.AddHttpClient<SimulatorConnector>(client => { client.BaseAddress = options.BaseAddress; client.Timeout = options.Timeout; });
        services.AddHostedService<AdministrativeDispatchWorker>();
        return services;
    }
}

internal sealed record ConnectorOptions(Uri BaseAddress, TimeSpan Timeout, TimeSpan PollInterval, TimeSpan RetryDelay, TimeSpan Lease)
{
    internal static ConnectorOptions From(IConfiguration section)
    {
        // Host configuration only: tenants and payloads never choose the remote address.
        if (!Uri.TryCreate(section["SimulatorBaseUrl"], UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https")
            || uri.UserInfo.Length > 0 || uri.Query.Length > 0 || !uri.AbsolutePath.EndsWith('/'))
            throw new InvalidOperationException("ExternalAdministration:SimulatorBaseUrl must be an absolute http(s) URL ending with '/'.");
        var options = new ConnectorOptions(uri, Milliseconds(section, "TimeoutMilliseconds", 5000, 100, 60000),
            Milliseconds(section, "PollMilliseconds", 1000, 50, 60000), Milliseconds(section, "RetryMilliseconds", 2000, 50, 600000),
            Milliseconds(section, "LeaseMilliseconds", 30000, 1000, 600000));
        if (options.Lease <= options.Timeout * 2) throw new InvalidOperationException("ExternalAdministration lease must exceed twice the timeout.");
        return options;
    }
    private static TimeSpan Milliseconds(IConfiguration section, string key, int fallback, int min, int max)
    {
        var value = section.GetValue<int?>(key) ?? fallback;
        if (value < min || value > max) throw new InvalidOperationException($"ExternalAdministration:{key} must be between {min} and {max}.");
        return TimeSpan.FromMilliseconds(value);
    }
}
