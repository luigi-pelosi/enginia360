using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using Enginia360.Workshop.Contracts;
using Xunit;

public sealed class WorkshopOwnActualTimeTests
{
    [Theory]
    [InlineData(typeof(RecordOwnActualTimeCommand))]
    [InlineData(typeof(CorrectOwnActualTimeCommand))]
    public void Commands_are_closed_immutable_exact_numeric_contracts_without_actor_input(Type type)
    {
        Assert.True(type.IsSealed);
        Assert.Equal(JsonUnmappedMemberHandling.Disallow, type.GetCustomAttribute<JsonUnmappedMemberHandlingAttribute>()?.UnmappedMemberHandling);
        Assert.Equal(JsonNumberHandling.Strict, type.GetCustomAttribute<JsonNumberHandlingAttribute>()?.Handling);
        Assert.DoesNotContain(type.GetProperties(), p => p.Name is "TenantId" or "MembershipId" or "InternalIdentityId" or "OperatorId" or "LegalEntityId" or "SiteId");
        foreach (var property in type.GetProperties()) Assert.Contains(typeof(System.Runtime.CompilerServices.IsExternalInit), property.SetMethod!.ReturnParameter.GetRequiredCustomModifiers());
        Assert.Throws<JsonException>(() => JsonSerializer.Deserialize("{\"operatorId\":\"11111111-1111-4111-8111-111111111111\"}", type, new JsonSerializerOptions(JsonSerializerDefaults.Web)));
    }
    [Fact]
    public void Own_time_contracts_do_not_import_a_domain_or_persistence_implementation()
    {
        Assert.DoesNotContain(typeof(RecordOwnActualTimeCommand).Assembly.GetReferencedAssemblies(), x => x.Name!.StartsWith("Enginia360.") || x.Name.StartsWith("Npgsql") || x.Name.StartsWith("Microsoft.EntityFramework"));
        Assert.DoesNotContain(typeof(OwnActualTimeEntry).GetProperties(), p => p.Name.Contains("Price") || p.Name.Contains("Billed") || p.Name.Contains("Quantity") || p.Name.Contains("Stock") || p.Name.Contains("CommercialRevision"));
        Assert.Equal(typeof(int), typeof(OwnActualTimeEntry).GetProperty("DurationSeconds")!.PropertyType);
    }
}
