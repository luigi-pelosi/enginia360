using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.EntityFrameworkCore;
using Enginia360.Catalog.Contracts;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

public sealed class CatalogManagementTests
{
    private const string Route = "/api/v1/catalog/management";
    [Theory]
    [InlineData(CatalogKind.Article,"Part")]
    [InlineData(CatalogKind.Service,"Service")]
    public void Typed_management_kind_converts_only_at_existing_storage_boundary(CatalogKind kind,string stored)
    {
        Assert.Equal(stored,CatalogKinds.ToStored(kind));Assert.Equal(kind,CatalogKinds.FromStored(stored));
    }
    [Fact]
    public void Unknown_kind_never_becomes_a_default_article_or_service()
    {
        Assert.Throws<ArgumentOutOfRangeException>(()=>CatalogKinds.FromStored("Vehicle"));
        Assert.Throws<ArgumentOutOfRangeException>(()=>CatalogKinds.ToStored((CatalogKind)123));
    }
    [RuntimePostgreSqlTheory]
    [InlineData(1,"Article")]
    [InlineData(4,"Article")]
    [InlineData(1,"Service")]
    [InlineData(4,"Service")]
    public async Task Current_signed_bearer_consumes_configured_roles_and_persisted_management_not_workshop(int pool,string kind)
    {
        var tenant=Guid.NewGuid();var company=Guid.NewGuid();var identity=Guid.NewGuid();var member=Guid.NewGuid();
        var role=Guid.NewGuid();var assignment=Guid.NewGuid();var subject="catalog-management-"+identity;
        await using var admin=NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using (var seed=admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES(@identity,@issuer,@subject);
            INSERT INTO organization_access.tenants("Id","Name") VALUES(@tenant,'Synthetic MVP05');
            INSERT INTO organization_access.memberships VALUES(@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities("Id","TenantId","Name") VALUES(@company,@tenant,'Synthetic company');
            INSERT INTO organization_access.tenant_role_objects("Id","TenantId","Kind","Data","Revision")
            SELECT gen_random_uuid(),@tenant,'permission',jsonb_build_object('action',a,'legalEntityId',NULL,'siteId',NULL,'warehouseId',NULL),1
            FROM unnest(ARRAY['catalog.shared.read','catalog.shared.create','catalog.shared.edit']) a;
            INSERT INTO organization_access.tenant_role_objects VALUES(@role,@tenant,'role',jsonb_build_object('permissionIds',
            (SELECT jsonb_agg("Id"::text) FROM organization_access.tenant_role_objects WHERE "TenantId"=@tenant AND "Kind"='permission')),1);
            INSERT INTO organization_access.tenant_role_objects VALUES(@assignment,@tenant,'assignment',jsonb_build_object('membershipId',@member::text,'internalIdentityId',@identity::text,'active',true,'roleId',@role::text,
            'bindingHash',encode(sha256(convert_to(jsonb_build_array(@issuer::text,@subject::text)::text,'UTF8')),'hex')),1);

            """))
        {
            seed.Parameters.AddWithValue("identity",identity);seed.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer);seed.Parameters.AddWithValue("subject",subject);
            seed.Parameters.AddWithValue("tenant",tenant);seed.Parameters.AddWithValue("member",member);seed.Parameters.AddWithValue("company",company);
            seed.Parameters.AddWithValue("role",role);seed.Parameters.AddWithValue("assignment",assignment);await seed.ExecuteNonQueryAsync();
        }
        using var factory=new BindingApiFactory(pool);
        using var application=factory.WithWebHostBuilder(b=>b.UseSetting("Catalog:Enabled","true").UseSetting("Workshop:Enabled","false").UseSetting("Counterparties:Enabled","false").ConfigureTestServices(services=>
        {
            // BindingApiFactory owns only OrganizationAccess. Configure the actual
            // business owning pool explicitly rather than its localhost default.
            var db=Type.GetType("Enginia360.Catalog.CatalogDbContext, Enginia360.Catalog",true)!;
            var optionsType=typeof(DbContextOptions<>).MakeGenericType(db);
            var configurationType=typeof(Microsoft.EntityFrameworkCore.Infrastructure.IDbContextOptionsConfiguration<>).MakeGenericType(db);
            foreach(var descriptor in services.Where(x=>x.ServiceType==optionsType||x.ServiceType==configurationType).ToArray())services.Remove(descriptor);
            var options=(DbContextOptionsBuilder)Activator.CreateInstance(typeof(DbContextOptionsBuilder<>).MakeGenericType(db))!;
            var connection=new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!){MaxPoolSize=pool,MinPoolSize=1};
            options.UseNpgsql(connection.ConnectionString);services.AddSingleton(optionsType,options.Options);
        }));
        using var client=application.CreateClient(new(){AllowAutoRedirect=false});
        // Synthetic-only owning-connection diagnostic. Never serialize a connection
        // string or expose the exception from a production HTTP response.
        using(var diagnosticScope=application.Services.CreateScope())
        {
            var type=Type.GetType("Enginia360.Catalog.CatalogDbContext, Enginia360.Catalog",true)!;
            var owning=(DbContext)diagnosticScope.ServiceProvider.GetRequiredService(type);
            var destination=new NpgsqlConnectionStringBuilder(owning.Database.GetConnectionString());
            Assert.Equal("postgres",destination.Host);Assert.Equal(pool,destination.MaxPoolSize);
            try { await owning.Database.OpenConnectionAsync();await owning.Database.CloseConnectionAsync(); }
            catch(System.Data.Common.DbException error)
            {
                Assert.Fail($"Synthetic management owning connection {destination.Host}:{destination.Port}; {error.GetType().Name}; SqlState={error.SqlState}; {error.Message}; inner={error.InnerException?.GetType().Name}: {error.InnerException?.Message}");
            }
        }
        var anonymous=await client.GetAsync(Route);Assert.Equal(HttpStatusCode.Unauthorized,anonymous.StatusCode);Assert.Contains("no-store",anonymous.Headers.CacheControl!.ToString());
        client.DefaultRequestHeaders.Authorization=new("Bearer",factory.Token(subject,Guid.NewGuid()));
        var create=new {commandId=Guid.NewGuid(),operation="create",itemId=(Guid?)null,expectedRevision=0,authorityVersion=1,kind,label="Synthetic independent "+kind};
        async Task AuthorityFixture(int version,string direction)
        {
            // Explicit synthetic owner staging only; the application never selects
            // or switches authority. The real owner CLI is exercised separately.
            await using var stage=admin.CreateCommand("""
                INSERT INTO catalog.authority_history("CommandId","TenantId","Version","Direction","SourceId","ProfileId","CompanyIds","ActorMembershipId","VerificationReference")
                VALUES(gen_random_uuid(),@tenant,@version,@direction,gen_random_uuid(),gen_random_uuid(),ARRAY[@company],@member,gen_random_uuid())
                """);
            stage.Parameters.AddWithValue("tenant",tenant);stage.Parameters.AddWithValue("company",company);stage.Parameters.AddWithValue("member",member);
            stage.Parameters.AddWithValue("version",version);stage.Parameters.AddWithValue("direction",direction);await stage.ExecuteNonQueryAsync();
        }
        async Task RefusedAuthority(string state)
        {
            var reply=await client.PostAsJsonAsync(Route+"/commands",create);Assert.Equal(HttpStatusCode.Conflict,reply.StatusCode);
            var body=await reply.Content.ReadFromJsonAsync<JsonElement>();Assert.Equal(state,body.GetProperty("state").GetString());
            await using var effects=admin.CreateCommand("SELECT count(*) FROM catalog.management_audit WHERE \"TenantId\"=@tenant");
            effects.Parameters.AddWithValue("tenant",tenant);Assert.Equal(0L,await effects.ExecuteScalarAsync());
        }
        await RefusedAuthority("missing");
        await AuthorityFixture(1,"ExternalToEnginia360");await RefusedAuthority("external");
        await AuthorityFixture(2,"Enginia360ToExternal");await RefusedAuthority("stale_authority");
        create=create with {authorityVersion=2};
        var accepted=await client.PostAsJsonAsync(Route+"/commands",create);Assert.Equal(HttpStatusCode.Created,accepted.StatusCode);
        Assert.Contains("no-store",accepted.Headers.CacheControl!.ToString());
        var original=await accepted.Content.ReadFromJsonAsync<JsonElement>();var snapshot=original.GetProperty("snapshot");var id=snapshot.GetProperty("id").GetGuid();
        var read=await client.GetFromJsonAsync<JsonElement>(Route+"?id="+id);
        Assert.Equal(snapshot.GetRawText(),read.GetProperty("detail").GetRawText());
        using(var scope=application.Services.CreateScope())
        {
            var accessor=scope.ServiceProvider.GetRequiredService<Microsoft.AspNetCore.Http.IHttpContextAccessor>();
            accessor.HttpContext=new Microsoft.AspNetCore.Http.DefaultHttpContext { User=new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity([
                new(System.Security.Claims.ClaimTypes.NameIdentifier,identity.ToString("D")),new("enginia360:verified-issuer",BindingApiFactory.Issuer),new("enginia360:external-subject",subject)],"Synthetic direct consumer")) };
            try
            {
                var legacy=await scope.ServiceProvider.GetRequiredService<IWorkshopCatalog>().Find(tenant,id,CancellationToken.None);
                Assert.NotNull(legacy);Assert.Equal(CatalogKinds.ToStored(CatalogKinds.FromStored(legacy.Kind)),legacy.Kind);
                Assert.Equal(kind=="Article"?"Part":"Service",legacy.Kind);Assert.Equal(1,legacy.Version);Assert.Equal(create.label,legacy.Label);
            }
            finally { accessor.HttpContext=null; }
        }
        var edit=create with {commandId=Guid.NewGuid(),operation="edit",itemId=(Guid?)id,expectedRevision=1,label="Updated "+kind};
        Assert.Equal(HttpStatusCode.Created,(await client.PostAsJsonAsync(Route+"/commands",edit)).StatusCode);
        Assert.Equal(HttpStatusCode.Conflict,(await client.PostAsJsonAsync(Route+"/commands",edit with {commandId=Guid.NewGuid()})).StatusCode);
        Assert.Equal(HttpStatusCode.Conflict,(await client.PostAsJsonAsync(Route+"/commands",edit with {commandId=Guid.NewGuid(),expectedRevision=2,kind=kind=="Article"?"Service":"Article"})).StatusCode);
        var current=await client.GetFromJsonAsync<JsonElement>(Route+"?id="+id);
        Assert.Equal(2,current.GetProperty("detail").GetProperty("revision").GetInt32());
        Assert.Equal(edit.label,current.GetProperty("detail").GetProperty("label").GetString());
        // Reconsume the unchanged historical port after the canonical edit: same
        // Id/storage kind, latest Version/Label, while the accepted snapshot stays v1.
        using(var scope=application.Services.CreateScope())
        {
            var accessor=scope.ServiceProvider.GetRequiredService<Microsoft.AspNetCore.Http.IHttpContextAccessor>();
            accessor.HttpContext=new Microsoft.AspNetCore.Http.DefaultHttpContext { User=new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity([
                new(System.Security.Claims.ClaimTypes.NameIdentifier,identity.ToString("D")),new("enginia360:verified-issuer",BindingApiFactory.Issuer),new("enginia360:external-subject",subject)],"Synthetic direct consumer")) };
            try
            {
                var legacy=await scope.ServiceProvider.GetRequiredService<IWorkshopCatalog>().Find(tenant,id,CancellationToken.None);
                Assert.NotNull(legacy);Assert.Equal(id,legacy.Id);Assert.Equal(kind=="Article"?"Part":"Service",legacy.Kind);
                Assert.Equal(2,legacy.Version);Assert.Equal(edit.label,legacy.Label);
                Assert.Equal(1,snapshot.GetProperty("revision").GetInt32());Assert.Equal(create.label,snapshot.GetProperty("label").GetString());
                Console.WriteLine("MVP05_IWORKSHOP_CATALOG_AFTER_EDIT "+JsonSerializer.Serialize(new {current=legacy,acceptedSnapshot=snapshot}));
            }
            finally { accessor.HttpContext=null; }
        }
        var replay=await (await client.PostAsJsonAsync(Route+"/commands",create)).Content.ReadFromJsonAsync<JsonElement>();
        Assert.Equal("replayed",replay.GetProperty("state").GetString());Assert.Equal(snapshot.GetRawText(),replay.GetProperty("snapshot").GetRawText());
        Assert.Equal(HttpStatusCode.BadRequest,(await client.PostAsync(Route+"/commands",new StringContent("{\"operation\":\"delete\",\"operation\":\"create\"}",System.Text.Encoding.UTF8,"application/json"))).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest,(await client.GetAsync(Route+"?id=AAAAAAAA-0000-0000-0000-000000000001")).StatusCode);
        await using(var revoke=admin.CreateCommand("UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"||'{\"permissionIds\":[]}'::jsonb,\"Revision\"=2 WHERE \"Id\"=@role"))
        {revoke.Parameters.AddWithValue("role",role);await revoke.ExecuteNonQueryAsync();}
        Assert.Equal(HttpStatusCode.Forbidden,(await client.GetAsync(Route)).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden,(await client.PostAsJsonAsync(Route+"/commands",create)).StatusCode);
        await using(var disable=admin.CreateCommand("INSERT INTO organization_access.membership_access_state VALUES(@member,@tenant,false,1)"))
        {disable.Parameters.AddWithValue("member",member);disable.Parameters.AddWithValue("tenant",tenant);await disable.ExecuteNonQueryAsync();}
        Assert.Contains((await client.GetAsync(Route)).StatusCode,new[]{HttpStatusCode.Unauthorized,HttpStatusCode.Forbidden});
        // The whole ephemeral database is discarded by the acceptance runner;
        // immutable command/audit history is deliberately not deleted here.
    }
}
