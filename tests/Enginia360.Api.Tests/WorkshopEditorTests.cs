using System.Globalization;
using System.Reflection;
using System.Text.Json.Serialization;
using Enginia360.Workshop;
using Enginia360.Workshop.Contracts;
using Xunit;

// R03.a offline guards: exact numeric boundary, closed command contract, ownership boundaries. Runtime behavior is in scripts/run-r03a-tests.py.
public sealed class WorkshopEditorTests
{
    private static readonly Assembly Workshop = typeof(WorkshopModule).Assembly;
    private static Type Internal(string name) => Workshop.GetType("Enginia360.Workshop." + name) ?? throw new InvalidOperationException(name);
    private static decimal D(string text) => decimal.Parse(text, CultureInfo.InvariantCulture);
    private static bool Exceeds(params string[] nets)
    {
        var lineType = Internal("CommercialLine");
        var list = (System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(lineType))!;
        var payer = Guid.NewGuid();
        foreach (var net in nets)
        {
            var line = Activator.CreateInstance(lineType)!;
            lineType.GetProperty("NetAmount")!.SetValue(line, D(net));
            lineType.GetProperty("PayerId")!.SetValue(line, payer);
            lineType.GetProperty("TaxRate")!.SetValue(line, 22m);
            list.Add(line);
        }
        var method = Internal("EditorEndpoints").GetMethod("ExceedsSummaryLimit", BindingFlags.Static | BindingFlags.NonPublic)!;
        return (bool)method.Invoke(null, [list])!;
    }

    [Fact]
    public void Summary_limit_accepts_exactly_the_numeric_18_6_total_and_rejects_the_next_micro_unit()
    {
        // 819672131147.540983 + HALF_UP6 22% tax 180327868852.459016 = 999999999999.999999 (downstream maximum).
        Assert.False(Exceeds("819672131147.540983"));
        Assert.True(Exceeds("819672131147.540984"));
        Assert.True(Exceeds("999999999998.000001"));
        Assert.False(Exceeds("0.000001", "1.000000"));
    }

    [Fact]
    public void Summary_limit_aggregates_all_rows_before_tax_not_per_row()
    {
        // Two rows below the limit individually, over it together.
        Assert.False(Exceeds("500000000000.000000"));
        Assert.True(Exceeds("500000000000.000000", "500000000000.000000"));
        // Tax of the aggregate is rounded once: 0.000002 + 0.000002 -> 0.000001 tax, never two zero taxes.
        var rounding = Internal("CommercialEndpoints").GetMethod("RoundMoney", BindingFlags.Static | BindingFlags.NonPublic)!;
        Assert.Equal(0.000001m, rounding.Invoke(null, [(0.000002m + 0.000002m) * 22m / 100m]));
        Assert.Equal(0m, rounding.Invoke(null, [0.000002m * 22m / 100m]));
    }

    [Fact]
    public void Server_owned_limits_and_structure_version_are_explicit_not_defaults()
    {
        var endpoints = Internal("EditorEndpoints");
        Assert.Equal(1, endpoints.GetField("StructurePolicyVersion", BindingFlags.Static | BindingFlags.NonPublic)!.GetRawConstantValue());
        Assert.Equal(1000, endpoints.GetField("MaxActiveLines", BindingFlags.Static | BindingFlags.NonPublic)!.GetRawConstantValue());
        Assert.Equal(100, endpoints.GetField("MaxActiveGroups", BindingFlags.Static | BindingFlags.NonPublic)!.GetRawConstantValue());
    }

    [Fact]
    public void Command_contract_is_closed_and_public_contracts_carry_the_real_working_group()
    {
        var attribute = typeof(EditorCommand).GetCustomAttribute<JsonUnmappedMemberHandlingAttribute>();
        Assert.Equal(JsonUnmappedMemberHandling.Disallow, attribute?.UnmappedMemberHandling);
        Assert.Contains(typeof(ReservationLine).GetProperties(), x => x.Name == "WorkingGroupId" && x.PropertyType == typeof(Guid));
        Assert.Contains(typeof(EditorCapabilities).GetProperties(), x => x.Name == "MaterialStructureEdit");
        Assert.All(new[] { typeof(EditorCommand), typeof(WorkshopEditReceipt), typeof(WorkshopEditorContract), typeof(LinePolicyContract) }, x => Assert.True(x.IsSealed));
        Assert.DoesNotContain(typeof(EditorCommand).Assembly.GetReferencedAssemblies(), x => x.Name!.StartsWith("Microsoft.EntityFramework") || x.Name.StartsWith("Npgsql") || x.Name.StartsWith("Enginia360."));
    }

    [Fact]
    public void Workshop_sources_never_query_inventory_tables_or_physically_delete()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !Directory.Exists(Path.Combine(directory.FullName, "src", "Modules", "Workshop"))) directory = directory.Parent;
        Assert.NotNull(directory);
        foreach (var file in Directory.EnumerateFiles(Path.Combine(directory.FullName, "src", "Modules", "Workshop"), "*.cs", SearchOption.AllDirectories))
        {
            if (file.Contains("/obj/") || file.Contains("/bin/")) continue;
            var text = File.ReadAllText(file);
            Assert.False(System.Text.RegularExpressions.Regex.IsMatch(text, @"\b(FROM|JOIN|INTO|UPDATE)\s+inventory\.", System.Text.RegularExpressions.RegexOptions.IgnoreCase), file);
            Assert.DoesNotContain("DELETE FROM", text, StringComparison.OrdinalIgnoreCase);
        }
    }
}
