using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

public sealed class DocumentInventoryTests
{
    private const string Route="/api/v1/documents";
    [RuntimePostgreSqlTheory]
    [InlineData(1,"Load")][InlineData(4,"Load")][InlineData(1,"Unload")][InlineData(4,"Unload")]
    [InlineData(1,"Transfer")][InlineData(4,"Transfer")][InlineData(1,"None")][InlineData(4,"None")]
    public async Task Persisted_multiline_confirmation_current_policy_and_bearer_parser_boundary(int pool,string effect)
    {
        var tenant=Guid.NewGuid();var company=Guid.NewGuid();var other=Guid.NewGuid();var site=Guid.NewGuid();var warehouse=Guid.NewGuid();var destination=Guid.NewGuid();
        var identity=Guid.NewGuid();var member=Guid.NewGuid();var role=Guid.NewGuid();var assignment=Guid.NewGuid();var item=Guid.NewGuid();var service=Guid.NewGuid();var type=Guid.NewGuid();var loadType=Guid.NewGuid();var unloadType=Guid.NewGuid();var subject="mvp07-"+identity;
        await using var admin=NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using(var seed=admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES(@identity,@issuer,@subject);
            INSERT INTO organization_access.tenants VALUES(@tenant,'Synthetic MVP07 API');
            INSERT INTO organization_access.memberships VALUES(@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities VALUES(@company,@tenant,'Authorized'),(@other,@tenant,'Hidden');
            INSERT INTO organization_access.sites VALUES(@site,@company,@tenant,'Synthetic site');
            INSERT INTO organization_access.warehouses VALUES(@warehouse,@site,@company,@tenant,'Source'),(@destination,@site,@company,@tenant,'Destination');
            INSERT INTO catalog.items VALUES(@item,@tenant,@company,'Part','Synthetic article',1),(@service,@tenant,@company,'Service','Synthetic service',1);
            BEGIN;
            INSERT INTO document_types.definitions VALUES(@type,@tenant,@company,1),(@loadType,@tenant,@company,1),(@unloadType,@tenant,@company,1);
            INSERT INTO document_types.versions("TenantId","LegalEntityId","DocumentTypeId","Revision","Label","Effect") VALUES(@tenant,@company,@type,1,'Synthetic type',@effect),(@tenant,@company,@loadType,1,'Initial confirmed Load','Load'),(@tenant,@company,@unloadType,1,'Concurrent Unload','Unload');
            COMMIT;
            INSERT INTO organization_access.tenant_role_objects
            SELECT gen_random_uuid(),@tenant,'permission',jsonb_build_object('action',a,'legalEntityId',@company::text,'siteId',@site::text,'warehouseId',NULL),1
            FROM unnest(ARRAY['documents.read','documents.save','documents.confirm']) a;
            INSERT INTO organization_access.tenant_role_objects
            SELECT gen_random_uuid(),@tenant,'permission',jsonb_build_object('action',a,'legalEntityId',@company::text,'siteId',NULL,'warehouseId',NULL),1
            FROM unnest(ARRAY['inventory.policy.read','inventory.policy.manage']) a;
            INSERT INTO organization_access.tenant_role_objects
            SELECT gen_random_uuid(),@tenant,'permission',jsonb_build_object('action',a,'legalEntityId',@company::text,'siteId',@site::text,'warehouseId',w::text),1
            FROM unnest(ARRAY['inventory.document-effects.apply','inventory.quantities.read']) a CROSS JOIN unnest(ARRAY[@warehouse,@destination]) w;
            INSERT INTO organization_access.tenant_role_objects VALUES(@role,@tenant,'role',jsonb_build_object('permissionIds',(SELECT jsonb_agg("Id"::text) FROM organization_access.tenant_role_objects WHERE "TenantId"=@tenant AND "Kind"='permission')),1);
            INSERT INTO organization_access.tenant_role_objects VALUES(@assignment,@tenant,'assignment',jsonb_build_object('membershipId',@member::text,'internalIdentityId',@identity::text,'active',true,'roleId',@role::text,'bindingHash',encode(sha256(convert_to(jsonb_build_array(@issuer::text,@subject::text)::text,'UTF8')),'hex')),1);
            """))
        {
            foreach(var (name,value) in new[]{("tenant",tenant),("company",company),("other",other),("site",site),("warehouse",warehouse),("destination",destination),("identity",identity),("member",member),("role",role),("assignment",assignment),("item",item),("service",service),("type",type),("loadType",loadType),("unloadType",unloadType)})seed.Parameters.AddWithValue(name,value);
            seed.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer);seed.Parameters.AddWithValue("subject",subject);seed.Parameters.AddWithValue("effect",effect);await seed.ExecuteNonQueryAsync();
        }
        using var factory=new BindingApiFactory(pool);
        using var application=factory.WithWebHostBuilder(b=>b.UseSetting("Documents:Enabled","true").UseSetting("Workshop:Enabled","false").UseSetting("Catalog:Enabled","false").UseSetting("Counterparties:Enabled","false").ConfigureTestServices(services=>
        {
            // The actual owning context, not only OrganizationAccess (localhost:503 is NOT a fixture).
            var db=Type.GetType("Enginia360.Documents.DocumentsDbContext, Enginia360.Documents",true)!;
            var optionsType=typeof(DbContextOptions<>).MakeGenericType(db);var configurationType=typeof(Microsoft.EntityFrameworkCore.Infrastructure.IDbContextOptionsConfiguration<>).MakeGenericType(db);
            foreach(var descriptor in services.Where(x=>x.ServiceType==optionsType||x.ServiceType==configurationType).ToArray())services.Remove(descriptor);
            var options=(DbContextOptionsBuilder)Activator.CreateInstance(typeof(DbContextOptionsBuilder<>).MakeGenericType(db))!;
            options.UseNpgsql(new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!){MaxPoolSize=pool,MinPoolSize=1}.ConnectionString);services.AddSingleton(optionsType,options.Options);
        }));
        using var client=application.CreateClient(new(){AllowAutoRedirect=false});
        var anonymous=await client.GetAsync(Route);Assert.Equal(HttpStatusCode.Unauthorized,anonymous.StatusCode);Assert.Contains("no-store",anonymous.Headers.CacheControl!.ToString());
        client.DefaultRequestHeaders.Authorization=new("Bearer",factory.Token(subject,Guid.NewGuid()));
        var chooser=await client.GetFromJsonAsync<JsonElement>(Route);Assert.Equal(company,Assert.Single(chooser.GetProperty("companies").EnumerateArray()).GetProperty("id").GetGuid());
        var path=Route+"?legalEntityId="+company+"&siteId="+site;
        Assert.Equal(HttpStatusCode.Forbidden,(await client.GetAsync(Route+"?legalEntityId="+other)).StatusCode);
        object Line(Guid selected,string quantity,Guid? source=null,Guid? dest=null)=>new{id=Guid.NewGuid(),itemId=selected,catalogRevision=1,quantity,warehouseId=source,destinationWarehouseId=dest};
        object Draft(Guid selectedType,object[] lines)=>new{commandId=Guid.NewGuid(),operation="create",legalEntityId=company,siteId=site,documentId=(Guid?)null,expectedRevision=0,documentTypeId=selectedType,expectedTypeRevision=1,title="Synthetic "+effect,lines};
        async Task<JsonElement> Post(object payload,HttpStatusCode expected=HttpStatusCode.Created)
        {var response=await client.PostAsJsonAsync(Route+"/commands",payload);Assert.Equal(expected,response.StatusCode);Assert.Contains("no-store",response.Headers.CacheControl!.ToString());return await response.Content.ReadFromJsonAsync<JsonElement>();}
        object Confirm(JsonElement snapshot,int policyRevision=0)=>new{commandId=Guid.NewGuid(),operation="confirm",legalEntityId=company,siteId=site,documentId=snapshot.GetProperty("id").GetGuid(),expectedRevision=snapshot.GetProperty("revision").GetInt32(),expectedTypeRevision=1,expectedPolicyRevision=policyRevision};
        // Initial quantities ONLY by a confirmed Load, no stock seed.
        var opening=(await Post(Draft(loadType,[Line(item,"5",warehouse)]))).GetProperty("snapshot");await Post(Confirm(opening));
        var body=Draft(type,[Line(item,"1.000001",effect=="None"?null:warehouse,effect=="Transfer"?destination:null),Line(item,"0.999999",effect=="None"?null:warehouse,effect=="Transfer"?destination:null),Line(service,"7")]);
        var draft=(await Post(body)).GetProperty("snapshot");var id=draft.GetProperty("id").GetGuid();Assert.Equal(3,draft.GetProperty("lines").GetArrayLength());
        var before=await client.GetFromJsonAsync<JsonElement>(path+"&warehouseId="+warehouse);Assert.Equal("5.000000",before.GetProperty("balances")[0].GetProperty("quantity").GetString());
        var command=Confirm(draft);var confirmed=(await Post(command)).GetProperty("snapshot");Assert.Equal("Confirmed",confirmed.GetProperty("state").GetString());
        var replay=await Post(command,HttpStatusCode.OK);Assert.Equal("replayed",replay.GetProperty("state").GetString());Assert.Equal(confirmed.GetRawText(),replay.GetProperty("snapshot").GetRawText());
        await Post(Confirm(draft),HttpStatusCode.Conflict);
        var after=await client.GetFromJsonAsync<JsonElement>(path+"&warehouseId="+warehouse);Assert.Equal(effect switch{"Load"=>"7.000000","None"=>"5.000000",_=>"3.000000"},after.GetProperty("balances")[0].GetProperty("quantity").GetString());
        var read=await client.GetFromJsonAsync<JsonElement>(path+"&id="+id);Assert.Equal(confirmed.GetRawText(),read.GetProperty("detail").GetRawText());Assert.Equal(effect switch{"Transfer"=>4,"None"=>0,_=>2},read.GetProperty("ledger").GetArrayLength());
        long expectedAudit=4;
        // Real concurrent HTTP through each actual owning pool (1 and4). SQL
        // tests separately force physical waiters, rather than trusting scheduling.
        var available=effect switch { "Load"=>"7", "None"=>"5", _=>"3" };
        var discharges=new List<JsonElement>();
        for(var i=0;i<2;i++)discharges.Add((await Post(Draft(unloadType,[Line(item,available,warehouse)]))).GetProperty("snapshot"));
        expectedAudit+=2;
        var responses=await Task.WhenAll(discharges.Select(d=>client.PostAsJsonAsync(Route+"/commands",Confirm(d))));
        Assert.Single(responses,r=>r.StatusCode==HttpStatusCode.Created);Assert.Single(responses,r=>r.StatusCode==HttpStatusCode.Conflict);expectedAudit++;
        var refusal=await responses.Single(r=>r.StatusCode==HttpStatusCode.Conflict).Content.ReadFromJsonAsync<JsonElement>();Assert.Equal("insufficient_stock",refusal.GetProperty("state").GetString());
        var remaining=await client.GetFromJsonAsync<JsonElement>(path+"&warehouseId="+warehouse);Assert.Equal("0.000000",remaining.GetProperty("balances")[0].GetProperty("quantity").GetString());
        if(effect=="Transfer")
        {
            var restock=(await Post(Draft(loadType,[Line(item,"4",warehouse)]))).GetProperty("snapshot");await Post(Confirm(restock));expectedAudit+=2;
            var forward=(await Post(Draft(type,[Line(item,"1",warehouse,destination)]))).GetProperty("snapshot");
            var reverse=(await Post(Draft(type,[Line(item,"1",destination,warehouse)]))).GetProperty("snapshot");expectedAudit+=2;
            var transfers=await Task.WhenAll(client.PostAsJsonAsync(Route+"/commands",Confirm(forward)),client.PostAsJsonAsync(Route+"/commands",Confirm(reverse)));
            Assert.All(transfers,r=>Assert.Equal(HttpStatusCode.Created,r.StatusCode));expectedAudit+=2;
            var sourceStock=await client.GetFromJsonAsync<JsonElement>(path+"&warehouseId="+warehouse);var destinationStock=await client.GetFromJsonAsync<JsonElement>(path+"&warehouseId="+destination);
            Assert.Equal("4.000000",sourceStock.GetProperty("balances")[0].GetProperty("quantity").GetString());Assert.Equal("2.000000",destinationStock.GetProperty("balances")[0].GetProperty("quantity").GetString());
        }
        var json=JsonSerializer.Serialize(body);
        foreach(var hostile in new[]{json[..^1]+",\"title\":\"duplicate\"}",json.Replace("\"quantity\":\"1.000001\"","\"quantity\":1.0"),json.Replace("\"quantity\":\"1.000001\"","\"quantity\":\"1.0000001\""),json.Replace("\"expectedRevision\":0","\"expectedRevision\":1e999999"),json.Replace("Synthetic "+effect,"\\ud800"),json.Replace("Synthetic "+effect,"\\u0000"),new string('x',262145)})
        {
            var response=await client.PostAsync(Route+"/commands",new ChunkedContent(hostile));Assert.Equal(HttpStatusCode.BadRequest,response.StatusCode);
        }
        foreach(var q in new[]{"&siteId="+site,"&id=","&tenantId="+tenant,"&selection=unknown","&search=%00","&warehouseId=AAAAAAAA-0000-0000-0000-000000000001"})Assert.Equal(HttpStatusCode.BadRequest,(await client.GetAsync(path+q)).StatusCode);
        await using(var revoke=admin.CreateCommand("UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"||'{\"permissionIds\":[]}'::jsonb,\"Revision\"=2 WHERE \"Id\"=@role")){revoke.Parameters.AddWithValue("role",role);await revoke.ExecuteNonQueryAsync();}
        Assert.Equal(HttpStatusCode.Forbidden,(await client.GetAsync(path)).StatusCode);await Post(command,HttpStatusCode.Forbidden);
        await using var audit=admin.CreateCommand("SELECT count(*) FROM documents.command_audit WHERE \"TenantId\"=@tenant");audit.Parameters.AddWithValue("tenant",tenant);Assert.Equal(expectedAudit,await audit.ExecuteScalarAsync());
    }
    private sealed class ChunkedContent(string text):HttpContent
    {
        protected override bool TryComputeLength(out long length){length=0;return false;}
        protected override async Task SerializeToStreamAsync(Stream stream,TransportContext? context)
        {var bytes=Encoding.UTF8.GetBytes(text);for(var i=0;i<bytes.Length;i+=7)await stream.WriteAsync(bytes.AsMemory(i,Math.Min(7,bytes.Length-i)));}
    }
}
