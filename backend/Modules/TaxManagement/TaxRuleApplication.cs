using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Npgsql;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public static class TaxRuleApplication
{
    public static async Task<Dictionary<string,object?>> Read(AppDb db,Guid tenant,Guid id,bool write=false,bool share=false)
    {
        var root=(await Rows(db,"SELECT * FROM taxmanagement.tax_rules WHERE tenant_id=@t AND id=@id"+(write?" FOR UPDATE":share?" FOR SHARE":""),("t",tenant),("id",id))).SingleOrDefault()??throw new ApiException(404,"tax_rule_not_found","id");
        var versions=await Rows(db,"SELECT * FROM taxmanagement.tax_rule_versions WHERE tenant_id=@t AND tax_rule_id=@id ORDER BY version_number,id",("t",tenant),("id",id));
        var conditions=await Rows(db,"SELECT c.* FROM taxmanagement.tax_rule_conditions c JOIN taxmanagement.tax_rule_versions v ON v.tenant_id=c.tenant_id AND v.id=c.tax_rule_version_id WHERE v.tenant_id=@t AND v.tax_rule_id=@id ORDER BY c.field,c.id",("t",tenant),("id",id));
        foreach(var c in conditions)c["value"]=c["value"] is JsonElement j?j.Clone():JsonSerializer.Deserialize<JsonElement>((string)c["value"]!);
        foreach(var v in versions)v["conditions"]=conditions.Where(c=>(Guid)c["tax_rule_version_id"]! == (Guid)v["id"]!).ToArray();root["versions"]=versions;return root;
    }
    public static TaxRuleSnapshot Snapshot(Dictionary<string,object?> r)=>new((Guid)r["id"]!,(Guid)r["tenant_id"]!,r["company_id"] as Guid?,(Guid)r["country_id"]!,(Guid)r["tax_type_id"]!,(string)r["code"]!,(long)r["version"]!,((IEnumerable<Dictionary<string,object?>>)r["versions"]!).Select(v=>new TaxRuleVersion((Guid)v["id"]!,(int)v["version_number"]!,(Guid)v["tax_code_id"]!,(int)v["priority"]!,(string)v["operation_type"]!,(string)v["status"]!,(string)v["legal_reference"]!,(DateOnly)v["valid_from"]!,v["valid_to"] as DateOnly?,((IEnumerable<Dictionary<string,object?>>)v["conditions"]!).Select(c=>new TaxRuleCondition((Guid)c["id"]!,(string)c["field"]!,(string)c["operator"]!,(JsonElement)c["value"]!)).ToArray())).ToArray());
    public static void Expected(TaxRuleSnapshot root,long expected)
    {Require(root.Revision==expected,"tax_rule_stale_version",409,"expectedVersion");Require(root.Revision<TaxRules.MaxRevision,"tax_rule_version_exhausted",409,"expectedVersion");}
    private static Task Audit(HttpContext ctx,AppDb db,TaxRuleSnapshot r,string action,long? before)=>db.Audit(Security.State(ctx).User.Id,r.TenantId,action,"tax-rules",r.Id,new{before_version=before,version=before==null?1:before+1,rule_id=r.Id,company_id=r.CompanyId});
    private static async Task Bump(HttpContext ctx,AppDb db,TaxRuleSnapshot r,string action)
    {Require(await db.Execute("UPDATE taxmanagement.tax_rules SET version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id AND version=@v",("t",r.TenantId),("id",r.Id),("v",r.Revision))==1,"tax_rule_stale_version",409,"expectedVersion");await Audit(ctx,db,r,action,r.Revision);}
    private static async Task InsertVersion(HttpContext ctx,AppDb db,TaxRuleSnapshot root,TaxRuleVersion v)
    {
        await db.Execute("INSERT INTO taxmanagement.tax_rule_versions(id,tenant_id,tax_rule_id,version_number,tax_code_id,priority,operation_type,status,legal_reference,valid_from,valid_to,created_at,created_by) VALUES(@id,@t,@r,@n,@code,@p,@op,'DRAFT',@legal,@from,@to::date,clock_timestamp(),@actor)",("id",v.Id),("t",root.TenantId),("r",root.Id),("n",v.VersionNumber),("code",v.TaxCodeId),("p",v.Priority),("op",v.OperationType),("legal",v.LegalReference),("from",v.ValidFrom),("to",v.ValidTo),("actor",Security.State(ctx).User.Id));
        await InsertConditions(db,root.TenantId,v);
    }
    private static async Task InsertConditions(AppDb db,Guid tenant,TaxRuleVersion v)
    {foreach(var c in v.Conditions)await db.Execute("INSERT INTO taxmanagement.tax_rule_conditions(id,tenant_id,tax_rule_version_id,field,operator,value) VALUES(@id,@t,@v,@f,@op,@value::jsonb)",("id",c.Id),("t",tenant),("v",v.Id),("f",c.Field),("op",c.Operator),("value",c.Value.GetRawText()));}
    private static async Task RequireValid(AppDb db,TaxRuleSnapshot r,TaxRuleVersion v)
    {var issues=await TaxRuleReferences.Validate(db,r,v,false);if(issues.Count>0)throw new ApiException(400,issues[0].Code,issues[0].Field);}
    public static async Task<Dictionary<string,object?>> Create(HttpContext ctx,AppDb db,Guid tenant,JsonElement body,string action="create")
    {
        var o=Object(body,"values","versions");var v=Object(Required(o,"values"),"company_id","country_id","tax_type_id","code","name","description");
        var company=Id(v,"company_id");await TaxRuleReferences.Action(ctx,db,tenant,company,"tax-rules."+action);await CompanyTaxApplication.Actor(ctx,db,tenant);
        if(company!=null)await CompanyTaxApplication.Company(db,tenant,company.Value,true);
        var root=new TaxRuleSnapshot(Guid.NewGuid(),tenant,company,Id(v,"country_id",true)!.Value,Id(v,"tax_type_id",true)!.Value,Text(v,"code",50,true)!,1,[]);
        Require(v["code"].GetString()==root.Code,"tax_invalid_code",field:"code");
        var name=Text(v,"name",150,true)!;var description=Text(v,"description",10000);
        var versions=o.TryGetValue("versions",out var raw)?Array(raw,"versions",100).Select((x,i)=>Version(x,i+1)).ToArray():[];
        await TaxClassificationApplication.ValidateScope(db,root.CountryId,root.TaxTypeId);
        Require(await db.Scalar("SELECT id FROM foundation.country WHERE id=@id AND is_enabled",("id",root.CountryId)) is Guid,"tax_rule_invalid_reference",field:"country_id");
        foreach(var draft in versions)await RequireValid(db,root,draft);
        try {
            await db.Execute("INSERT INTO taxmanagement.tax_rules(id,tenant_id,company_id,country_id,tax_type_id,code,name,description,version,created_at,updated_at) VALUES(@id,@t,@c::uuid,@country,@type,@code,@name,@description::text,1,clock_timestamp(),clock_timestamp())",("id",root.Id),("t",tenant),("c",company),("country",root.CountryId),("type",root.TaxTypeId),("code",root.Code),("name",name),("description",description));
            foreach(var draft in versions)await InsertVersion(ctx,db,root,draft);
        }catch(PostgresException e) when(e.SqlState=="23505"){throw new ApiException(409,"tax_rule_exists","code");}
        await Audit(ctx,db,root,action,null);return await Read(db,tenant,root.Id);
    }
    public static async Task<Dictionary<string,object?>> Update(HttpContext ctx,AppDb db,Guid tenant,Guid id,JsonElement body)
    {
        var o=Object(body,"values","expectedVersion");var v=Object(Required(o,"values"),"name","description");Required(v,"description");
        var r=Snapshot(await Read(db,tenant,id,true));await TaxRuleReferences.Action(ctx,db,tenant,r.CompanyId,"tax-rules.update");Expected(r,Revision(o));await CompanyTaxApplication.Actor(ctx,db,tenant);
        Require(await db.Execute("UPDATE taxmanagement.tax_rules SET name=@n,description=@d::text,version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id AND version=@v",("n",Text(v,"name",150,true)),("d",Text(v,"description",10000)),("t",tenant),("id",id),("v",r.Revision))==1,"tax_rule_stale_version",409,"expectedVersion");await Audit(ctx,db,r,"update",r.Revision);return await Read(db,tenant,id);
    }
    public static async Task<Dictionary<string,object?>> Draft(HttpContext ctx,AppDb db,Guid tenant,Guid id,Guid? versionId,JsonElement body)
    {
        var o=Object(body,"values","conditions","expectedVersion");var r=Snapshot(await Read(db,tenant,id,true));await TaxRuleReferences.Action(ctx,db,tenant,r.CompanyId,"tax-rules.update");Expected(r,Revision(o));await CompanyTaxApplication.Actor(ctx,db,tenant);
        var old=versionId==null?null:r.Versions.SingleOrDefault(v=>v.Id==versionId)??throw new ApiException(404,"tax_rule_version_not_found","versionId");
        Require(old==null||old.Status=="DRAFT","tax_rule_draft_required",409,"versionId");
        var next=Version(body,old?.VersionNumber??(r.Versions.Count==0?1:r.Versions.Max(v=>v.VersionNumber)+1),versionId,true);await RequireValid(db,r,next);
        if(old==null)await InsertVersion(ctx,db,r,next);
        else {
            await db.Execute("DELETE FROM taxmanagement.tax_rule_conditions WHERE tenant_id=@t AND tax_rule_version_id=@v",("t",tenant),("v",versionId));
            await db.Execute("UPDATE taxmanagement.tax_rule_versions SET tax_code_id=@code,priority=@p,operation_type=@op,legal_reference=@legal,valid_from=@from,valid_to=@to::date WHERE tenant_id=@t AND id=@v AND status='DRAFT'",("code",next.TaxCodeId),("p",next.Priority),("op",next.OperationType),("legal",next.LegalReference),("from",next.ValidFrom),("to",next.ValidTo),("t",tenant),("v",versionId));await InsertConditions(db,tenant,next);
        }
        await Bump(ctx,db,r,old==null?"create_version":"update_version");return await Read(db,tenant,id);
    }
    public static async Task<List<TaxRuleCandidate>> Candidates(AppDb db,Guid tenant,Guid country,Guid type,string operation,Guid? company=null,bool allScopes=false)
    {
        var rows=await Rows(db,"SELECT DISTINCT r.id FROM taxmanagement.tax_rules r JOIN taxmanagement.tax_rule_versions v ON v.tenant_id=r.tenant_id AND v.tax_rule_id=r.id WHERE r.tenant_id=@t AND r.country_id=@c AND r.tax_type_id=@type AND v.operation_type=@op AND v.status='PUBLISHED' AND (@all OR r.company_id IS NULL OR r.company_id=@company::uuid) ORDER BY r.id",("t",tenant),("c",country),("type",type),("op",operation),("company",company),("all",allScopes));
        var result=new List<TaxRuleCandidate>();foreach(var row in rows){var r=Snapshot(await Read(db,tenant,(Guid)row["id"]!,share:true));result.AddRange(r.Versions.Where(v=>v.Status=="PUBLISHED"&&v.OperationType==operation).Select(v=>new TaxRuleCandidate(r.Id,r.Code,r.Revision,r.CompanyId,v)));}return result;
    }
    public static async Task<object> Validate(HttpContext ctx,AppDb db,Guid tenant,Guid id,Guid versionId,long expected,string action="validate")
    {
        var initial=Snapshot(await Read(db,tenant,id));await TaxRuleReferences.Action(ctx,db,tenant,initial.CompanyId,"tax-rules."+action);
        var initialVersion=initial.Versions.SingleOrDefault(v=>v.Id==versionId)??throw new ApiException(404,"tax_rule_version_not_found","versionId");
        await TaxRuleReferences.RulesetLock(db,tenant,initial.CountryId,initial.TaxTypeId,initialVersion.OperationType);
        var r=Snapshot(await Read(db,tenant,id,share:true));Expected(r,expected);
        var v=r.Versions.Single(x=>x.Id==versionId);Require(v.OperationType==initialVersion.OperationType,"tax_rule_stale_version",409,"expectedVersion");
        var issues=await TaxRuleReferences.Validate(db,r,v);var found=await Conflicts(db,r,v);var conflicts=new List<object>();
        foreach(var conflict in found)if(await TaxRuleReferences.Allowed(ctx,db,tenant,conflict.CompanyId,"tax-rules.read"))conflicts.Add(new{ruleId=conflict.RuleId,versionId=conflict.Version.Id,priority=conflict.Version.Priority,validFrom=conflict.Version.ValidFrom,validTo=conflict.Version.ValidTo});
        return new {valid=issues.Count==0&&found.Count==0,issues=found.Count>0?issues.Concat(new[]{new TaxRuleIssue("tax_rule_conflict","conditions")}).ToArray():issues,conflicts,hasRestrictedConflicts=found.Count!=conflicts.Count};
    }
    public static async Task<List<TaxRuleCandidate>> Conflicts(AppDb db,TaxRuleSnapshot r,TaxRuleVersion v)
    {
        var candidate=new TaxRuleCandidate(r.Id,r.Code,r.Revision,r.CompanyId,v);var others=await Candidates(db,r.TenantId,r.CountryId,r.TaxTypeId,v.OperationType,allScopes:true);
        return others.Where(x=>x.RuleId!=r.Id&&TaxRuleConflictDetector.Overlaps(candidate,x)).ToList();
    }
    public static async Task<Dictionary<string,object?>> Transition(HttpContext ctx,AppDb db,Guid tenant,Guid id,Guid versionId,long expected,bool publish)
    {
        // La chiave normativa precede qualsiasi lock esclusivo della radice.
        var initial=Snapshot(await Read(db,tenant,id));var initialVersion=initial.Versions.SingleOrDefault(v=>v.Id==versionId)??throw new ApiException(404,"tax_rule_version_not_found","versionId");
        await TaxRuleReferences.Action(ctx,db,tenant,initial.CompanyId,"tax-rules."+(publish?"publish":"withdraw"));
        await TaxRuleReferences.RulesetLock(db,tenant,initial.CountryId,initial.TaxTypeId,initialVersion.OperationType,true);
        var r=Snapshot(await Read(db,tenant,id,true));Expected(r,expected);var v=r.Versions.Single(x=>x.Id==versionId);
        Require(v.OperationType==initialVersion.OperationType,"tax_rule_stale_version",409,"expectedVersion");await CompanyTaxApplication.Actor(ctx,db,tenant);
        Require(v.Status==(publish?"DRAFT":"PUBLISHED"),publish?"tax_rule_draft_required":"tax_rule_published_required",409,"versionId");
        if(publish){
            var issues=await TaxRuleReferences.Validate(db,r,v);if(issues.Count>0)throw new ApiException(400,issues[0].Code,issues[0].Field);
            Require((await Conflicts(db,r,v)).Count==0,"tax_rule_conflict",409,"conditions");
            var overlapping=r.Versions.Where(x=>x.Status=="PUBLISHED"&&TaxRules.Overlaps(x.ValidFrom,x.ValidTo,v.ValidFrom,v.ValidTo)).ToArray();
            Require(overlapping.All(x=>x.ValidFrom<v.ValidFrom),"tax_rule_version_overlap",409,"valid_from");
            foreach(var previous in overlapping)await db.Execute("UPDATE taxmanagement.tax_rule_versions SET valid_to=@to WHERE tenant_id=@t AND id=@id",("to",v.ValidFrom.AddDays(-1)),("t",tenant),("id",previous.Id));
        }
        await db.Execute(publish?"UPDATE taxmanagement.tax_rule_versions SET status='PUBLISHED',published_at=clock_timestamp(),published_by=@a WHERE tenant_id=@t AND id=@id":"UPDATE taxmanagement.tax_rule_versions SET status='WITHDRAWN',withdrawn_at=clock_timestamp(),withdrawn_by=@a WHERE tenant_id=@t AND id=@id",("a",Security.State(ctx).User.Id),("t",tenant),("id",versionId));
        await Bump(ctx,db,r,publish?"publish":"withdraw");return await Read(db,tenant,id);
    }
}
