using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Enginia360.DocumentTypes.Contracts;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

public sealed class DocumentTypeManagementTests
{
    private const string Route = "/api/v1/document-types";
    [Fact]
    public void Supported_quantity_effects_are_exactly_four_not_custom_code()
    {
        Assert.Equal(new[] { "Load", "Unload", "Transfer", "None" }, Enum.GetNames<QuantityEffect>());
        Assert.False(Enum.IsDefined((QuantityEffect)123));
    }
    [RuntimePostgreSqlTheory]
    [InlineData(1,"Load")][InlineData(4,"Load")]
    [InlineData(1,"Unload")][InlineData(4,"Unload")]
    [InlineData(1,"Transfer")][InlineData(4,"Transfer")]
    [InlineData(1,"None")][InlineData(4,"None")]
    public async Task Signed_bearer_current_company_rights_versions_replay_input_and_revocation(int pool,string effect)
    {
        var tenant=Guid.NewGuid();var company=Guid.NewGuid();var other=Guid.NewGuid();var identity=Guid.NewGuid();var member=Guid.NewGuid();
        var role=Guid.NewGuid();var assignment=Guid.NewGuid();var subject="document-types-"+identity;
        await using var admin=NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using(var seed=admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES(@identity,@issuer,@subject);
            INSERT INTO organization_access.tenants("Id","Name") VALUES(@tenant,'Synthetic MVP06');
            INSERT INTO organization_access.memberships VALUES(@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities("Id","TenantId","Name") VALUES(@company,@tenant,'Authorized company'),(@other,@tenant,'Hidden company');
            INSERT INTO organization_access.tenant_role_objects
            SELECT gen_random_uuid(),@tenant,'permission',jsonb_build_object('action',a,'legalEntityId',@company::text,'siteId',NULL,'warehouseId',NULL),1
            FROM unnest(ARRAY['document-types.read','document-types.create','document-types.edit']) a;
            INSERT INTO organization_access.tenant_role_objects VALUES(@role,@tenant,'role',jsonb_build_object('permissionIds',
             (SELECT jsonb_agg("Id"::text) FROM organization_access.tenant_role_objects WHERE "TenantId"=@tenant AND "Kind"='permission')),1);
            INSERT INTO organization_access.tenant_role_objects VALUES(@assignment,@tenant,'assignment',jsonb_build_object('membershipId',@member::text,'internalIdentityId',@identity::text,'active',true,'roleId',@role::text,
             'bindingHash',encode(sha256(convert_to(jsonb_build_array(@issuer::text,@subject::text)::text,'UTF8')),'hex')),1);
            """))
        {
            seed.Parameters.AddWithValue("identity",identity);seed.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer);seed.Parameters.AddWithValue("subject",subject);
            seed.Parameters.AddWithValue("tenant",tenant);seed.Parameters.AddWithValue("member",member);seed.Parameters.AddWithValue("company",company);seed.Parameters.AddWithValue("other",other);
            seed.Parameters.AddWithValue("role",role);seed.Parameters.AddWithValue("assignment",assignment);await seed.ExecuteNonQueryAsync();
        }
        using var factory=new BindingApiFactory(pool);
        using var application=factory.WithWebHostBuilder(b=>b.UseSetting("DocumentTypes:Enabled","true").UseSetting("Catalog:Enabled","false").UseSetting("Workshop:Enabled","false").UseSetting("Counterparties:Enabled","false").ConfigureTestServices(services=>
        {
            var db=Type.GetType("Enginia360.DocumentTypes.DocumentTypesDbContext, Enginia360.DocumentTypes",true)!;
            var optionsType=typeof(DbContextOptions<>).MakeGenericType(db);
            var configurationType=typeof(Microsoft.EntityFrameworkCore.Infrastructure.IDbContextOptionsConfiguration<>).MakeGenericType(db);
            foreach(var descriptor in services.Where(x=>x.ServiceType==optionsType||x.ServiceType==configurationType).ToArray())services.Remove(descriptor);
            var options=(DbContextOptionsBuilder)Activator.CreateInstance(typeof(DbContextOptionsBuilder<>).MakeGenericType(db))!;
            var connection=new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!){MaxPoolSize=pool,MinPoolSize=1};
            options.UseNpgsql(connection.ConnectionString);services.AddSingleton(optionsType,options.Options);
        }));
        using var client=application.CreateClient(new(){AllowAutoRedirect=false});
        var anonymous=await client.GetAsync(Route);Assert.Equal(HttpStatusCode.Unauthorized,anonymous.StatusCode);Assert.Contains("no-store",anonymous.Headers.CacheControl!.ToString());
        client.DefaultRequestHeaders.Authorization=new("Bearer",factory.Token(subject,Guid.NewGuid()));
        var chooser=await client.GetFromJsonAsync<JsonElement>(Route);
        Assert.Equal(company,Assert.Single(chooser.GetProperty("companies").EnumerateArray()).GetProperty("id").GetGuid());
        Assert.Equal(JsonValueKind.Null,chooser.GetProperty("selectedCompanyId").ValueKind);
        Assert.Equal(HttpStatusCode.Forbidden,(await client.GetAsync(Route+"?legalEntityId="+other)).StatusCode);
        var path=Route+"?legalEntityId="+company;
        var create=new {commandId=Guid.NewGuid(),operation="create",legalEntityId=company,documentTypeId=(Guid?)null,expectedRevision=0,label="Synthetic "+effect,effect};
        var accepted=await client.PostAsJsonAsync(Route+"/commands",create);Assert.Equal(HttpStatusCode.Created,accepted.StatusCode);Assert.Contains("no-store",accepted.Headers.CacheControl!.ToString());
        var first=await accepted.Content.ReadFromJsonAsync<JsonElement>();var snapshot=first.GetProperty("snapshot");var id=snapshot.GetProperty("id").GetGuid();
        Assert.Equal(company,snapshot.GetProperty("legalEntityId").GetGuid());Assert.Equal(effect,snapshot.GetProperty("effect").GetString());
        var edit=create with {commandId=Guid.NewGuid(),operation="edit",documentTypeId=(Guid?)id,expectedRevision=1,label="Changed "+effect,effect=effect=="None"?"Load":"None"};
        Assert.Equal(HttpStatusCode.Created,(await client.PostAsJsonAsync(Route+"/commands",edit)).StatusCode);
        Assert.Equal(HttpStatusCode.Conflict,(await client.PostAsJsonAsync(Route+"/commands",edit with {commandId=Guid.NewGuid()})).StatusCode);
        var historical=await client.GetFromJsonAsync<JsonElement>(path+"&id="+id+"&revision=1");Assert.Equal(2,historical.GetProperty("detail").GetProperty("revision").GetInt32());
        Assert.Equal(snapshot.GetRawText(),historical.GetProperty("selectedVersion").GetRawText());Assert.Equal(2,historical.GetProperty("history").GetArrayLength());
        var replay=await (await client.PostAsJsonAsync(Route+"/commands",create)).Content.ReadFromJsonAsync<JsonElement>();Assert.Equal("replayed",replay.GetProperty("state").GetString());Assert.Equal(snapshot.GetRawText(),replay.GetProperty("snapshot").GetRawText());
        Assert.Equal(HttpStatusCode.Conflict,(await client.PostAsJsonAsync(Route+"/commands",create with {label="Collision"})).StatusCode);
        // Real parser boundary: no jsonb overflow503 or invalid Unicode500.
        var json=JsonSerializer.Serialize(create);
        var hostile=new[]{json.Replace("\"expectedRevision\":0","\"expectedRevision\":1e999999"),json.Replace("\"expectedRevision\":0","\"expectedRevision\":true"),json.Replace("\"label\":\"Synthetic "+effect+"\"","\"label\":\"\\u0000\""),json.Replace("\"label\":\"Synthetic "+effect+"\"","\"label\":\"\\ud800\""),json.Replace("\"effect\":\""+effect+"\"","\"effect\":0"),json.Replace("\"effect\":\""+effect+"\"","\"effect\":\"formula\""),json[..^1]+",\"effect\":\"None\"}",json[..^1]+",\"tenantId\":\""+tenant+"\"}",new string('x',8193)};
        foreach(var body in hostile)Assert.Equal(HttpStatusCode.BadRequest,(await client.PostAsync(Route+"/commands",new StringContent(body,Encoding.UTF8,"application/json"))).StatusCode);
        foreach(var query in new[]{"&legalEntityId="+company,"&revision=0","&id="+id+"&revision=2147483648","&id=AAAAAAAA-0000-0000-0000-000000000001","&id=","&tenantId="+tenant,"&search=%00"})
            Assert.Equal(HttpStatusCode.BadRequest,(await client.GetAsync(path+query)).StatusCode);
        Assert.Equal(HttpStatusCode.Created,(await client.PostAsJsonAsync(Route+"/commands",create with {commandId=Guid.NewGuid(),label=string.Concat(Enumerable.Repeat("😀",100))})).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest,(await client.PostAsJsonAsync(Route+"/commands",create with {commandId=Guid.NewGuid(),label=string.Concat(Enumerable.Repeat("😀",101))})).StatusCode);
        await using(var revoke=admin.CreateCommand("UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"||'{\"permissionIds\":[]}'::jsonb,\"Revision\"=2 WHERE \"Id\"=@role"))
        {revoke.Parameters.AddWithValue("role",role);await revoke.ExecuteNonQueryAsync();}
        Assert.Equal(HttpStatusCode.Forbidden,(await client.GetAsync(path)).StatusCode);Assert.Equal(HttpStatusCode.Forbidden,(await client.PostAsJsonAsync(Route+"/commands",create)).StatusCode);
        await using(var disabled=admin.CreateCommand("INSERT INTO organization_access.membership_access_state VALUES(@member,@tenant,false,1)"))
        {disabled.Parameters.AddWithValue("member",member);disabled.Parameters.AddWithValue("tenant",tenant);await disabled.ExecuteNonQueryAsync();}
        Assert.Contains((await client.GetAsync(Route)).StatusCode,new[]{HttpStatusCode.Unauthorized,HttpStatusCode.Forbidden});
        await using var audit=admin.CreateCommand("SELECT count(*) FROM document_types.command_audit WHERE \"TenantId\"=@tenant");audit.Parameters.AddWithValue("tenant",tenant);Assert.Equal(3L,await audit.ExecuteScalarAsync());
    }
}
