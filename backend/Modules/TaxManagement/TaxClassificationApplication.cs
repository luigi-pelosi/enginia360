using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Npgsql;

namespace Enginia360.Modules.TaxManagement;

/// <summary>Adattatore limitato ai riferimenti esterni: nessun import o modifica degli aggregati Catalogo/BP.</summary>
public static class ClassificationSubjectReference
{
    public static async Task Require(AppDb db,ClassificationKind kind,Guid tenant,Guid subject,bool forWrite)
    {
        // Il lock SHARE sulla riga serializza archiviazione e assegnazione senza cambiare la versione del soggetto.
        var status=await db.Scalar("SELECT status FROM masterdata."+kind.SubjectTable+" WHERE tenant_id=@t AND id=@id FOR SHARE",("t",tenant),("id",subject)) as string;
        ClassificationTimeline.Require(status!=null,"tax_profile_subject_not_found",404,"subjectId");
        ClassificationTimeline.Require(!forWrite || status!="ARCHIVED","tax_profile_subject_unavailable",409,"subjectId");
    }
}

public static class TaxClassificationApplication
{
    public static async Task<List<Dictionary<string,object?>>> Rows(AppDb db,string sql,params (string Name,object? Value)[] args)
    {
        var rows=new List<Dictionary<string,object?>>();
        await using var cmd=await db.Command(sql,args);await using var reader=await cmd.ExecuteReaderAsync();
        while(await reader.ReadAsync()) {
            var row=new Dictionary<string,object?>();
            for(var i=0;i<reader.FieldCount;i++) row[reader.GetName(i)]=reader.IsDBNull(i)?null:reader.GetValue(i);
            rows.Add(row);
        }
        return rows;
    }
    public static async Task<Guid> Gate(HttpContext ctx,AppDb db,string permission,string resource)
    {
        await Security.Authorize(ctx,permission);
        ClassificationTimeline.Require(db.Database.CurrentTransaction!=null,"server_error",500);
        var tenant=Security.State(ctx).Tenant(ctx,resource);
        ClassificationTimeline.Require(tenant!=null,"tax_classification_tenant_required",field:"tenantId");
        ClassificationTimeline.Require(await db.Scalar("SELECT id FROM foundation.tenant WHERE id=@t AND is_enabled",("t",tenant)) is Guid,"tax_classification_tenant_not_found",404,"tenantId");
        return tenant!.Value;
    }
    public static Task Lock(AppDb db,ClassificationKind kind,Guid tenant,Guid subject,bool write=true)
        =>db.Execute("SELECT "+(write?"pg_advisory_xact_lock":"pg_advisory_xact_lock_shared")+"(hashtextextended(@key,0))",("key","tax-profile:"+kind.Name+":"+tenant.ToString()+":"+subject.ToString()));
    public static async Task<Dictionary<string,object?>> Classification(AppDb db,ClassificationKind kind,Guid tenant,Guid id,bool update=false)
    {
        return (await Rows(db,"SELECT c.*,t.code AS tax_type_code,t.is_active AS tax_type_active,g.iso_code AS country_iso_code FROM taxmanagement."+kind.ClassificationTable+" c JOIN taxmanagement.tax_types t ON t.id=c.tax_type_id JOIN foundation.country g ON g.id=c.country_id WHERE c.tenant_id=@t AND c.id=@id"+(update?" FOR UPDATE OF c":" FOR SHARE OF c"),("t",tenant),("id",id))).SingleOrDefault()??throw new ApiException(404,"tax_classification_not_found","classification_id");
    }
    public static TaxClassificationIdentity Identity(Dictionary<string,object?> row)=>new((Guid)row["id"]!,(Guid)row["country_id"]!,(Guid)row["tax_type_id"]!,(bool)row["is_active"]!,(string)row["tax_type_code"]! == "VAT" && (bool)row["tax_type_active"]!,(long)row["version"]!);
    public static async Task ValidateScope(AppDb db,Guid country,Guid type)
    {
        ClassificationTimeline.Require(await db.Scalar("SELECT id FROM foundation.country WHERE id=@id",("id",country)) is Guid,"tax_classification_invalid_country",field:"country_id");
        ClassificationTimeline.Require(await db.Scalar("SELECT id FROM taxmanagement.tax_types WHERE id=@id AND code='VAT' AND is_active",("id",type)) is Guid,"tax_classification_type_not_supported",field:"tax_type_id");
    }
    public static Task<List<Dictionary<string,object?>>> Profiles(AppDb db,ClassificationKind kind,Guid tenant,Guid subject)
        =>Rows(db,"SELECT p.*,c.code AS classification_code,c.name AS classification_name,c.is_active AS classification_is_active FROM taxmanagement."+kind.ProfileTable+" p JOIN taxmanagement."+kind.ClassificationTable+" c ON c.tenant_id=p.tenant_id AND c.id=p."+kind.ClassificationColumn+" WHERE p.tenant_id=@t AND p."+kind.SubjectColumn+"=@subject ORDER BY p.valid_from,p.revision",("t",tenant),("subject",subject));
    public static ClassificationProfile Profile(Dictionary<string,object?> row,ClassificationKind kind)=>new((Guid)row["id"]!,(Guid)row["country_id"]!,(Guid)row["tax_type_id"]!,(Guid)row[kind.ClassificationColumn]!,(DateOnly)row["valid_from"]!,row["valid_to"] as DateOnly?,(long)row["revision"]!);
    public static async Task<ClassificationProfilePlan> Assign(HttpContext ctx,AppDb db,ClassificationKind kind,Guid tenant,Guid subject,ClassificationProfile next,long expected,bool schedule)
    {
        var before=await Profiles(db,kind,tenant,subject);
        var timeline=new ClassificationTimeline(before.Select(x=>Profile(x,kind)));
        var plan=timeline.Plan(next,expected,schedule);
        var classifier=await Classification(db,kind,tenant,next.ClassificationId);
        Identity(classifier).RequireAssignable(next.CountryId,next.TaxTypeId);
        var predecessor=before.SingleOrDefault(x=>x["id"] as Guid?==plan.PredecessorId);
        try {
            if(plan.PredecessorId!=null) await db.Execute("UPDATE taxmanagement."+kind.ProfileTable+" SET valid_to=@to WHERE tenant_id=@t AND "+kind.SubjectColumn+"=@subject AND id=@id",("to",plan.PredecessorValidTo),("t",tenant),("subject",subject),("id",plan.PredecessorId));
            await db.Execute("INSERT INTO taxmanagement."+kind.ProfileTable+"(id,tenant_id,"+kind.SubjectColumn+",country_id,tax_type_id,"+kind.ClassificationColumn+",valid_from,valid_to,revision,created_at,created_by) VALUES(@id,@t,@subject,@country,@type,@classification,@from,@to::date,@revision,clock_timestamp(),@actor)",("id",next.Id),("t",tenant),("subject",subject),("country",next.CountryId),("type",next.TaxTypeId),("classification",next.ClassificationId),("from",next.ValidFrom),("to",next.ValidTo),("revision",plan.Revision),("actor",Security.State(ctx).User.Id));
        } catch(PostgresException e) when(e.SqlState=="23P01") {throw new ApiException(409,"tax_profile_overlap","valid_from");}
        catch(PostgresException e) when(e.SqlState=="23505") {throw new ApiException(409,"tax_profile_stale_version","expectedVersion");}
        await db.Audit(Security.State(ctx).User.Id,tenant,schedule?"schedule":"assign",kind.ProfileResource,subject,new {
            subject_id=subject,
            before=new {version=timeline.Version,predecessor=predecessor==null?null:new {id=plan.PredecessorId,valid_to=predecessor["valid_to"]}},
            after=new {version=plan.Revision,profile=new {id=next.Id,country_id=next.CountryId,tax_type_id=next.TaxTypeId,classification_id=next.ClassificationId,valid_from=next.ValidFrom,valid_to=next.ValidTo,revision=plan.Revision},predecessor=plan.PredecessorId==null?null:new {id=plan.PredecessorId,valid_to=plan.PredecessorValidTo}}
        });
        return plan;
    }
    public static async Task AssignInitial(HttpContext ctx,AppDb db,ClassificationKind kind,Guid tenant,Guid subject,JsonElement taxProfiles)
    {
        ClassificationTimeline.Require(taxProfiles.ValueKind==JsonValueKind.Array && taxProfiles.GetArrayLength()<=100,"tax_profile_invalid_initial_profiles",field:"taxProfiles");
        if(taxProfiles.GetArrayLength()==0)return;
        var authorizedTenant=await Gate(ctx,db,kind.ProfileResource+".assign",kind.ProfileResource);
        ClassificationTimeline.Require(authorizedTenant==tenant,"tax_profile_tenant_mismatch",403,"tenantId");
        var profiles=taxProfiles.EnumerateArray().Select(x=>ClassificationInput.Profile(x,kind)).OrderBy(x=>x.CountryId).ThenBy(x=>x.TaxTypeId).ThenBy(x=>x.ValidFrom).ToArray();
        // Validare tutto l'insieme iniziale prima degli inserimenti, distinguendo ogni ambito paese/tipo.
        _=new ClassificationTimeline(profiles.Select((x,i)=>x with {Revision=i+1}));
        await ClassificationSubjectReference.Require(db,kind,tenant,subject,true);
        await Lock(db,kind,tenant,subject);
        long version=0;
        foreach(var profile in profiles) version=(await Assign(ctx,db,kind,tenant,subject,profile,version,false)).Revision;
    }
}

public interface ITaxClassificationResolver
{
    Task<Dictionary<string,object?>> ResolveItem(Guid tenant,Guid item,Guid country,Guid taxType,DateOnly date);
    Task<Dictionary<string,object?>> ResolvePartner(Guid tenant,Guid partner,Guid country,Guid taxType,DateOnly date);
}

/// <summary>La risoluzione storica non applica l'idoneita corrente della classificazione o del soggetto.</summary>
public sealed class TaxClassificationResolver(AppDb db):ITaxClassificationResolver
{
    public Task<Dictionary<string,object?>> ResolveItem(Guid tenant,Guid item,Guid country,Guid taxType,DateOnly date)=>Resolve(ClassificationKind.Item,tenant,item,country,taxType,date);
    public Task<Dictionary<string,object?>> ResolvePartner(Guid tenant,Guid partner,Guid country,Guid taxType,DateOnly date)=>Resolve(ClassificationKind.Partner,tenant,partner,country,taxType,date);
    private async Task<Dictionary<string,object?>> Resolve(ClassificationKind kind,Guid tenant,Guid subject,Guid country,Guid type,DateOnly date)
    {
        await ClassificationSubjectReference.Require(db,kind,tenant,subject,false);
        await TaxClassificationApplication.Lock(db,kind,tenant,subject,false);
        // Query limitata a data e ambito: nessun Unknown automatico o ripiego su altro ambito/ultima riga.
        var rows=await TaxClassificationApplication.Rows(db,"SELECT p.*,c.code AS classification_code,c.name AS classification_name,c.is_active AS classification_is_active FROM taxmanagement."+kind.ProfileTable+" p JOIN taxmanagement."+kind.ClassificationTable+" c ON c.tenant_id=p.tenant_id AND c.id=p."+kind.ClassificationColumn+" WHERE p.tenant_id=@t AND p."+kind.SubjectColumn+"=@subject AND p.country_id=@country AND p.tax_type_id=@type AND p.valid_from<=@date AND (p.valid_to IS NULL OR p.valid_to>=@date) LIMIT 2",("t",tenant),("subject",subject),("country",country),("type",type),("date",date));
        var selected=new ClassificationTimeline(rows.Select(x=>TaxClassificationApplication.Profile(x,kind))).Resolve(country,type,date);
        return rows.Single(x=>(Guid)x["id"]! == selected.Id);
    }
}
