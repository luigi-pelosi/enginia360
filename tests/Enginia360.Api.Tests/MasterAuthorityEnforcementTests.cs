using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Enginia360.Counterparties.Contracts;
using Microsoft.AspNetCore.Hosting;
using Xunit;

public sealed class MasterAuthorityEnforcementTests : IClassFixture<TestApiFactory>
{
    private readonly TestApiFactory factory;
    public MasterAuthorityEnforcementTests(TestApiFactory factory) => this.factory = factory;

    [Theory]
    [InlineData("/api/v1/counterparties/authority?legalEntityId=11111111-1111-4111-8111-111111111111")]
    [InlineData("/api/v1/counterparties/11111111-1111-4111-8111-111111111111/edit-state?legalEntityId=11111111-1111-4111-8111-111111111111")]
    public async Task Authority_and_edit_state_require_real_authentication_not_identity_headers(string path)
    {
        using var app = factory.WithWebHostBuilder(builder => builder.UseSetting("Counterparties:Enabled", "true"));
        using var client = app.CreateClient();
        client.DefaultRequestHeaders.Add("X-Tenant-Id", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Identity-Subject", Guid.NewGuid().ToString());
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(path)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PutAsJsonAsync("/api/v1/counterparties/11111111-1111-4111-8111-111111111111", new {})).StatusCode);
    }

    [Fact]
    public void Missing_command_authority_and_revision_are_not_fabricated_by_transport()
    {
        var value = JsonSerializer.Deserialize<UpdateCounterpartyRequest>("{}")!;
        Assert.Null(value.CommandId);
        Assert.Null(value.AuthorityVersion);
        Assert.Null(value.ExpectedRevision);
        var id = Guid.NewGuid();
        var command = new UpdateCounterpartyRequest(id,"Name","SYNTHETIC","Office",id,7,3);
        var roundtrip = JsonSerializer.Deserialize<UpdateCounterpartyRequest>(JsonSerializer.Serialize(command));
        Assert.Equal(command, roundtrip);
    }
}
