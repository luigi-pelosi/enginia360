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

public sealed class DocumentDevelopmentTests
{
    private const string Route="/api/v1/documents";
    [RuntimePostgreSqlTheory]
    [InlineData(1)][InlineData(4)]
    public async Task Confirmed_sources_partial_stage_capacity_and_merged_origins_through_owning_HTTP(int pool)
    {
        const string effect="None";
        var tenant=Guid.NewGuid();var company=Guid.NewGuid();var other=Guid.NewGuid();var site=Guid.NewGuid();var warehouse=Guid.NewGuid();var destination=Guid.NewGuid();
        var identity=Guid.NewGuid();var member=Guid.NewGuid();var role=Guid.NewGuid();var assignment=Guid.NewGuid();var item=Guid.NewGuid();var service=Guid.NewGuid();var type=Guid.NewGuid();var loadType=Guid.NewGuid();var unloadType=Guid.NewGuid();var subject="mvp08-"+identity;
        await using var admin=NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using(var seed=admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES(@identity,@issuer,@subject);
            INSERT INTO organization_access.tenants VALUES(@tenant,'Synthetic MVP08 API');
            INSERT INTO organization_access.memberships VALUES(@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities VALUES(@company,@tenant,'Authorized'),(@other,@tenant,'Hidden');
            INSERT INTO organization_access.sites VALUES(@site,@company,@tenant,'Synthetic site');
            INSERT INTO organization_access.warehouses VALUES(@warehouse,@site,@company,@tenant,'Source'),(@destination,@site,@company,@tenant,'Destination');
            INSERT INTO catalog.items VALUES(@item,@tenant,@company,'Part','Synthetic article',1),(@service,@tenant,@company,'Service','Synthetic service',1);
            BEGIN;
            INSERT INTO document_types.definitions VALUES(@type,@tenant,@company,1),(@loadType,@tenant,@company,1),(@unloadType,@tenant,@company,1);
            INSERT INTO document_types.versions("TenantId","LegalEntityId","DocumentTypeId","Revision","Label","Effect") VALUES(@tenant,@company,@type,1,'Synthetic type',@effect),(@tenant,@company,@loadType,1,'Initial confirmed Load','Load'),(@tenant,@company,@unloadType,1,'Concurrent Unload','Unload');
            INSERT INTO document_types.passages VALUES(@tenant,@company,@loadType,@type,1),(@tenant,@company,@loadType,@unloadType,1),(@tenant,@company,@type,@unloadType,1);
            INSERT INTO document_types.passage_versions("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId","Revision","Enabled","AllowCrossSite") VALUES(@tenant,@company,@loadType,@type,1,true,false),(@tenant,@company,@loadType,@unloadType,1,true,false),(@tenant,@company,@type,@unloadType,1,true,false);
            COMMIT;
            INSERT INTO organization_access.tenant_role_objects
            SELECT gen_random_uuid(),@tenant,'permission',jsonb_build_object('action',a,'legalEntityId',@company::text,'siteId',@site::text,'warehouseId',NULL),1
            FROM unnest(ARRAY['documents.read','documents.save','documents.confirm','documents.develop']) a;
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
        var sourceDraft=(await Post(Draft(loadType,[Line(item,"3",warehouse)]))).GetProperty("snapshot");
        var source=(await Post(Confirm(sourceDraft))).GetProperty("snapshot");
        object Allocation(JsonElement src,string quantity)=>new{sourceDocumentId=src.GetProperty("id").GetGuid(),sourceLineId=src.GetProperty("lines")[0].GetProperty("id").GetGuid(),quantity,expectedPathRevision=1};
        object Developed(Guid selectedType,JsonElement[] sources,string[] quantities,bool merge=false)
        {
            var lines=sources.Select((src,i)=>new{id=Guid.NewGuid(),itemId=item,catalogRevision=1,quantity=quantities[i],warehouseId=selectedType==type?(Guid?)null:warehouse,destinationWarehouseId=(Guid?)null,origins=new[]{Allocation(src,quantities[i])}}).Cast<object>().ToArray();
            if(merge)lines=[new{id=Guid.NewGuid(),itemId=item,catalogRevision=1,quantity="3.000000",warehouseId=(Guid?)null,destinationWarehouseId=(Guid?)null,origins=sources.Select((src,i)=>Allocation(src,quantities[i])).ToArray()}];
            return new{commandId=Guid.NewGuid(),operation="develop",legalEntityId=company,siteId=site,documentId=(Guid?)null,expectedRevision=0,documentTypeId=selectedType,expectedTypeRevision=1,title="Synthetic derived",lines};
        }
        var drafts=new List<JsonElement>();
        for(var i=0;i<2;i++)drafts.Add((await Post(Developed(type,[source],["2"]))).GetProperty("snapshot"));
        var sourceRead=await client.GetFromJsonAsync<JsonElement>(path+"&id="+source.GetProperty("id").GetGuid());
        var stage=sourceRead.GetProperty("stages").EnumerateArray().Single(s=>s.GetProperty("destinationTypeId").GetGuid()==type);
        Assert.Equal(0m,decimal.Parse(stage.GetProperty("committed").GetString()!,System.Globalization.CultureInfo.InvariantCulture));
        Assert.Equal(4m,decimal.Parse(stage.GetProperty("plannedNotReserved").GetString()!,System.Globalization.CultureInfo.InvariantCulture));
        foreach(var d in drafts){var read=await client.GetFromJsonAsync<JsonElement>(path+"&id="+d.GetProperty("id").GetGuid());Assert.Empty(read.GetProperty("ledger").EnumerateArray());}
        var commands=drafts.Select(d=>Confirm(d)).ToArray();
        var race=await Task.WhenAll(commands.Select(c=>client.PostAsJsonAsync(Route+"/commands",c)));
        Assert.Single(race,r=>r.StatusCode==HttpStatusCode.Created);Assert.Single(race,r=>r.StatusCode==HttpStatusCode.Conflict);
        var losing=Array.FindIndex(race,r=>r.StatusCode==HttpStatusCode.Conflict);
        Assert.Equal("insufficient_residual",(await race[losing].Content.ReadFromJsonAsync<JsonElement>()).GetProperty("state").GetString());
        var lostRead=await client.GetFromJsonAsync<JsonElement>(path+"&id="+drafts[losing].GetProperty("id").GetGuid());Assert.Equal("Draft",lostRead.GetProperty("detail").GetProperty("state").GetString());Assert.Empty(lostRead.GetProperty("ledger").EnumerateArray());
        var winning=1-losing;await Post(commands[winning],HttpStatusCode.OK);await Post(Confirm(drafts[winning]),HttpStatusCode.Conflict);
        // Independent stage may use all three again, producing its normal effect.
        var independent=(await Post(Developed(unloadType,[source],["3"]))).GetProperty("snapshot");await Post(Confirm(independent));
        var balance=await client.GetFromJsonAsync<JsonElement>(path+"&warehouseId="+warehouse);Assert.Equal("0.000000",balance.GetProperty("balances")[0].GetProperty("quantity").GetString());
        var more=new List<JsonElement>();
        for(var i=0;i<2;i++){var draft=(await Post(Draft(loadType,[Line(item,"3",warehouse)]))).GetProperty("snapshot");more.Add((await Post(Confirm(draft))).GetProperty("snapshot"));}
        var mergedPayload=Developed(type,more.ToArray(),["1.000001","1.999999"],true);var merged=(await Post(mergedPayload)).GetProperty("snapshot");
        Assert.Equal(2,merged.GetProperty("lines")[0].GetProperty("origins").GetArrayLength());Assert.Equal("3.000000",merged.GetProperty("lines")[0].GetProperty("quantity").GetString());
        var mergedConfirm=Confirm(merged);var accepted=(await Post(mergedConfirm)).GetProperty("snapshot");await Post(mergedConfirm,HttpStatusCode.OK);
        var hop=(await Post(Developed(unloadType,[accepted],["1"]))).GetProperty("snapshot");await Post(Confirm(hop));
        var hopRead=await client.GetFromJsonAsync<JsonElement>(path+"&id="+hop.GetProperty("id").GetGuid());Assert.Equal(accepted.GetProperty("id").GetGuid(),hopRead.GetProperty("detail").GetProperty("lines")[0].GetProperty("origins")[0].GetProperty("sourceDocumentId").GetGuid());
        var ordinary=new{commandId=Guid.NewGuid(),operation="save",legalEntityId=company,siteId=site,documentId=drafts[losing].GetProperty("id").GetGuid(),expectedRevision=1,documentTypeId=type,expectedTypeRevision=1,title="Cannot strip",lines=new[]{Line(item,"1")}};
        Assert.Equal("development_plan_required",(await Post(ordinary,HttpStatusCode.Conflict)).GetProperty("state").GetString());
        var payload=JsonSerializer.Serialize(mergedPayload);
        async Task<string> OwnedFacts()
        {
            string[] tables=["documents.headers","documents.lines","documents.versions","documents.policy_versions","documents.balances","documents.ledger","documents.command_audit","documents.origins","document_types.definitions","document_types.versions","document_types.command_audit","document_types.passages","document_types.passage_versions","organization_access.tenant_role_objects","organization_access.membership_access_state","catalog.items"];
            var fields=tables.Select(table=>$"'{table}',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM {table} x WHERE \"TenantId\"=@tenant)");
            await using var read=admin.CreateCommand("SELECT jsonb_build_object("+string.Join(',',fields)+",'documents.snapshot_fence',(SELECT jsonb_agg(to_jsonb(x)) FROM documents.snapshot_fence x))::text");
            read.Parameters.AddWithValue("tenant",tenant);return (string)(await read.ExecuteScalarAsync())!;
        }
        var beforeHostile=await OwnedFacts();
        foreach(var hostile in new[]{payload[..^1]+",\"title\":\"duplicate\"}",payload.Replace("\"expectedPathRevision\":1","\"expectedPathRevision\":-1"),payload.Replace("\"quantity\":\"1.000001\"","\"quantity\":1.0"),payload.Replace("\"sourceLineId\":","\"unknown\":true,\"sourceLineId\":"),payload.Replace("Synthetic derived","\\ud800",StringComparison.Ordinal),payload.Replace("\"quantity\":\"1.000001\"","\"quantity\":\"1e0\"",StringComparison.Ordinal),new string('x',262145)})
        {var response=await client.PostAsync(Route+"/commands",new ChunkedContent(hostile));Assert.Equal(HttpStatusCode.BadRequest,response.StatusCode);Assert.Equal(beforeHostile,await OwnedFacts());}
        Assert.Equal(HttpStatusCode.BadRequest,(await client.GetAsync(path+"&legalEntityId="+company)).StatusCode);Assert.Equal(beforeHostile,await OwnedFacts());
        var collision=payload.Replace("Synthetic derived","Different payload same command",StringComparison.Ordinal);Assert.NotEqual(payload,collision);
        Assert.Equal(HttpStatusCode.Conflict,(await client.PostAsync(Route+"/commands",new ChunkedContent(collision))).StatusCode);Assert.Equal(beforeHostile,await OwnedFacts());
        await using(var revoke=admin.CreateCommand("UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"||'{\"action\":\"documents.read\"}'::jsonb,\"Revision\"=2 WHERE \"TenantId\"=@tenant AND \"Kind\"='permission' AND \"Data\"->>'action'='documents.develop'"))
        {revoke.Parameters.AddWithValue("tenant",tenant);await revoke.ExecuteNonQueryAsync();}
        await Post(mergedConfirm,HttpStatusCode.Forbidden);await Post(mergedPayload,HttpStatusCode.Forbidden);
        var current=await client.GetFromJsonAsync<JsonElement>(path+"&id="+accepted.GetProperty("id").GetGuid());Assert.Equal("Confirmed",current.GetProperty("detail").GetProperty("state").GetString());
    }
    private sealed class ChunkedContent(string text):HttpContent
    {
        protected override bool TryComputeLength(out long length){length=0;return false;}
        protected override async Task SerializeToStreamAsync(Stream stream,TransportContext? context)
        {var bytes=Encoding.UTF8.GetBytes(text);for(var i=0;i<bytes.Length;i+=7)await stream.WriteAsync(bytes.AsMemory(i,Math.Min(7,bytes.Length-i)));}
    }
}
