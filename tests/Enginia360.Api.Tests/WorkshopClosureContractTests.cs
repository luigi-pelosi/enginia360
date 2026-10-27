using System.Reflection;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Enginia360.Integrations;
using Enginia360.Workshop.Contracts;
using Xunit;

// R03.c offline guards. Runtime behavior is in WorkshopClosureActionTests/WorkshopClosureSnapshotTests and scripts/run-r03c-*.py.
public sealed class WorkshopClosureContractTests
{
    [Fact]
    public void Registered_adapter_declares_the_simulator_and_never_a_real_erp()
    {
        var services = new ServiceCollection();
        services.AddExternalAdministration("Host=unused", new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?> { ["SimulatorBaseUrl"] = "https://synthetic.test/" }).Build());
        using var provider = services.BuildServiceProvider();
        Assert.Equal(new AdministrativeRuntime("SimulatorV1", 1), provider.GetRequiredService<AdministrativeRuntime>());
        Assert.Equal(new AdministrativeRuntime("Unavailable", 0), AdministrativeRuntime.Unavailable);
    }

    [Fact]
    public void Action_advice_is_a_read_model_without_actor_tenant_or_provider_endpoint_data()
    {
        var names = typeof(OrderClosureActions).GetProperties().Select(p => p.Name).Concat(typeof(AdministrativeRuntime).GetProperties().Select(p => p.Name)).ToArray();
        Assert.DoesNotContain(names, n => n.Contains("Tenant") || n.Contains("Operator") || n.Contains("Url") || n.Contains("Secret") || n.Contains("Account") || n.Contains("Request") && n != "CanRequestAdministrative" && n != "MayRequestReconciliation");
        Assert.All(typeof(OrderClosureActions).GetProperties(), p => Assert.Contains(typeof(System.Runtime.CompilerServices.IsExternalInit), p.SetMethod!.ReturnParameter.GetRequiredCustomModifiers()));
        Assert.DoesNotContain(typeof(OrderClosureActions).Assembly.GetReferencedAssemblies(), a => a.Name!.StartsWith("Enginia360.") && a.Name != "Enginia360.Workshop.Contracts" || a.Name.StartsWith("Npgsql"));
    }
}
