using Enginia360.Inventory;
using Enginia360.Inventory.Contracts;
using Xunit;

public sealed class InventoryArchitectureTests
{
    [Fact]
    public void Inventory_exposes_registration_only_and_references_only_public_module_contracts()
    {
        var assembly = typeof(InventoryModule).Assembly;
        Assert.Equal([typeof(InventoryModule)], assembly.GetExportedTypes());
        Assert.DoesNotContain(assembly.GetReferencedAssemblies(), a =>
            a.Name!.StartsWith("Enginia360.") && a.Name is not
                ("Enginia360.Inventory.Contracts" or "Enginia360.Workshop.Contracts"));
    }

    [Fact]
    public void Inventory_contracts_do_not_expose_orm_or_module_implementation_dependencies()
    {
        Assert.DoesNotContain(typeof(ReserveRequest).Assembly.GetReferencedAssemblies(), a =>
            a.Name!.StartsWith("Microsoft.") || a.Name.StartsWith("Npgsql") || a.Name.StartsWith("Enginia360."));
    }
}
