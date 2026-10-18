using Enginia360.Counterparties;
using Enginia360.Counterparties.Contracts;
using Xunit;

public sealed class CounterpartyArchitectureTests
{
    [Fact]
    public void Implementation_exposes_only_registration_and_no_other_module_implementation_dependency()
    {
        var assembly = typeof(CounterpartiesModule).Assembly;
        Assert.Equal([typeof(CounterpartiesModule)], assembly.GetExportedTypes());
        Assert.DoesNotContain(assembly.GetReferencedAssemblies(), a => a.Name == "Enginia360.Api" || (a.Name!.StartsWith("Enginia360.") && a.Name != "Enginia360.Counterparties.Contracts"));
    }
    [Fact]
    public void Contracts_expose_no_orm_or_implementation_dependency()
    {
        Assert.DoesNotContain(typeof(CounterpartyContract).Assembly.GetReferencedAssemblies(), a => a.Name!.StartsWith("Microsoft.") || a.Name.StartsWith("Npgsql") || a.Name == "Enginia360.Api" || a.Name == "Enginia360.Counterparties");
    }
    [Fact]
    public void Domain_types_are_internal_and_use_only_bcl_property_types()
    {
        var types = typeof(CounterpartiesModule).Assembly.GetTypes().Where(t => t.Namespace == "Enginia360.Counterparties.Domain").ToList();
        Assert.Equal(2, types.Count);
        Assert.All(types, t =>
        {
            Assert.False(t.IsPublic);
            Assert.All(t.GetProperties(), p => Assert.StartsWith("System", p.PropertyType.Namespace!));
        });
    }
}
