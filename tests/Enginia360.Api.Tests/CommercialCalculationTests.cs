using System.Reflection;
using Enginia360.Catalog;
using Enginia360.Catalog.Contracts;
using Enginia360.Workshop;
using Xunit;

public sealed class CommercialCalculationTests
{
    [Theory]
    [InlineData("0.0000004999", "0.000000")]
    [InlineData("0.0000005", "0.000001")]
    [InlineData("0.0000005001", "0.000001")]
    [InlineData("16.335", "16.335")]
    [InlineData("19.855", "19.855")]
    [InlineData("36.19", "36.19")]
    public void Production_money_rounding_uses_explicit_half_up_boundaries(string input, string expected)
    {
        // Arithmetic primitive only: these inputs are not additional authorized fiscal profiles.
        var type = typeof(WorkshopModule).Assembly.GetType("Enginia360.Workshop.CommercialEndpoints");
        var method = type?.GetMethod("RoundMoney", BindingFlags.Static | BindingFlags.NonPublic);
        Assert.NotNull(method);
        var value = decimal.Parse(input, System.Globalization.CultureInfo.InvariantCulture);
        var result = Assert.IsType<decimal>(method.Invoke(null, [value]));
        Assert.Equal(decimal.Parse(expected, System.Globalization.CultureInfo.InvariantCulture), result);
    }

    [Fact]
    public void Catalog_implementation_exposes_only_registration_and_depends_only_on_contracts()
    {
        Assert.Equal([typeof(CatalogModule)], typeof(CatalogModule).Assembly.GetExportedTypes());
        Assert.All(typeof(CatalogModule).Assembly.GetReferencedAssemblies().Where(x=>x.Name!.StartsWith("Enginia360.")), x=>Assert.EndsWith(".Contracts", x.Name));
        Assert.DoesNotContain(typeof(CatalogChoice).Assembly.GetReferencedAssemblies(), x=>x.Name!.StartsWith("Microsoft.") || x.Name.StartsWith("Npgsql") || x.Name.StartsWith("Enginia360."));
    }
}
