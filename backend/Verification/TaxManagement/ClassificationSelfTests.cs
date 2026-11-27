using System.Reflection;
using System.Text.Json;
using Enginia360.Modules.TaxManagement;
using Enginia360.Shared.Validation;
namespace Enginia360.Verification.TaxManagement;

public static class ClassificationSelfTests
{
    public static void Run()
    {
        var count=0;
        void Assert(bool condition,string label) {if(!condition)throw new Exception("Classification assertion failed: "+label);count++;}
        void Reject(Action action,string code,string? field=null) {
            try {action();}catch(ApiException e) when(e.Code==code && (field==null || e.Field==field)) {count++;return;}
            throw new Exception("Expected "+code+" field="+field);
        }
        Assert(Assembly.GetExecutingAssembly().GetType("Enginia360.Modules.TaxManagement.ClassificationTimeline")!=null,"temporal kernel available");
        var country=Guid.NewGuid();var otherCountry=Guid.NewGuid();var type=Guid.NewGuid();var classifier=Guid.NewGuid();var from=new DateOnly(2026,1,1);
        ClassificationProfile P(DateOnly? start=null,DateOnly? end=null,long revision=1,Guid? nation=null,Guid? taxType=null)=>new(Guid.NewGuid(),nation??country,taxType??type,classifier,start??from,end,revision);
        var empty=new ClassificationTimeline([]);
        Assert(empty.Version==0,"empty subject stream starts at zero");
        var initial=P(revision:0);var plan=empty.Plan(initial,0,false);
        Assert(plan.Revision==1 && plan.PredecessorId==null,"first revision one");
        var current=P();var timeline=new ClassificationTimeline([current]);
        Assert(timeline.Resolve(country,type,from).Id==current.Id,"inclusive start");
        Assert(timeline.Resolve(country,type,DateOnly.MaxValue).Id==current.Id,"open end");
        var finite=P(end:from.AddDays(10));var finiteTimeline=new ClassificationTimeline([finite]);
        Assert(finiteTimeline.Resolve(country,type,finite.ValidTo!.Value).Id==finite.Id,"inclusive end");
        Reject(()=>finiteTimeline.Resolve(country,type,from.AddDays(11)),"tax_profile_not_found","date");
        Reject(()=>timeline.Resolve(otherCountry,type,from),"tax_profile_not_found");
        Reject(()=>timeline.Resolve(country,Guid.NewGuid(),from),"tax_profile_not_found");
        Reject(()=>timeline.Resolve(country,type,from.AddDays(-1)),"tax_profile_not_found");
        Reject(()=>timeline.Plan(P(start:from.AddDays(1),revision:0),1,false),"tax_profile_overlap","valid_from");
        Reject(()=>timeline.Plan(P(revision:0),1,true),"tax_profile_overlap");
        var next=P(start:from.AddMonths(1),revision:0);var schedule=timeline.Plan(next,1,true);
        Assert(schedule.PredecessorId==current.Id && schedule.PredecessorValidTo==next.ValidFrom.AddDays(-1) && schedule.Revision==2,"schedule closes only covering predecessor");
        var independent=timeline.Plan(P(nation:otherCountry,revision:0),1,false);
        Assert(independent.Revision==2 && independent.PredecessorId==null,"scope differs but stream is subject-wide");
        Assert(timeline.Plan(P(taxType:Guid.NewGuid(),revision:0),1,false).Revision==2,"type independent overlap scope");
        var adjacent=P(start:from.AddDays(11),revision:0);
        Assert(finiteTimeline.Plan(adjacent,1,false).Revision==2,"adjacent dates allowed");
        Reject(()=>finiteTimeline.Plan(P(start:from.AddDays(10),revision:0),1,false),"tax_profile_overlap");
        var future=P(start:from.AddMonths(3),revision:8);
        var multi=new ClassificationTimeline([current with {ValidTo=from.AddMonths(1).AddDays(-1)},future]);
        Assert(multi.Version==8,"max all revisions not count");
        Reject(()=>multi.Plan(P(start:from.AddMonths(1),end:future.ValidFrom,revision:0),8,true),"tax_profile_overlap");
        var gap=multi.Plan(P(start:from.AddMonths(1),end:future.ValidFrom.AddDays(-1),revision:0),8,true);
        Assert(gap.Revision==9 && gap.PredecessorId==null,"gap insert no implicit close");
        Reject(()=>multi.Plan(P(nation:otherCountry,revision:0),1,false),"tax_profile_stale_version","expectedVersion");
        Reject(()=>empty.Plan(initial,-1,false),"tax_profile_invalid_expected_version");
        Reject(()=>ClassificationTimeline.CheckVersion(ClassificationTimeline.MaxRevision,ClassificationTimeline.MaxRevision),"tax_profile_version_exhausted");
        Reject(()=>new ClassificationTimeline([current,current with {Id=Guid.NewGuid(),CountryId=otherCountry}]),"tax_profile_duplicate_revision");
        Reject(()=>new ClassificationTimeline([current,P(start:from.AddDays(1),revision:2)]),"tax_profile_overlap");
        Reject(()=>empty.Plan(P(end:from.AddDays(-1),revision:0),0,false),"tax_profile_invalid_interval","valid_to");
        Reject(()=>empty.Plan(initial with {CountryId=Guid.Empty},0,false),"tax_profile_invalid_reference");
        var min=P(start:DateOnly.MinValue,revision:0);
        Assert(empty.Plan(min,0,true).PredecessorId==null,"minimum date never subtracts without predecessor");
        var leap=P(start:new DateOnly(2024,2,1));
        Assert(new ClassificationTimeline([leap]).Plan(P(start:new DateOnly(2024,3,1),revision:0),1,true).PredecessorValidTo==new DateOnly(2024,2,29),"leap day closure");
        var identity=new TaxClassificationIdentity(classifier,country,type,true,true,5);
        identity.RequireAssignable(country,type);count++;
        Reject(()=>identity.RequireAssignable(otherCountry,type),"tax_profile_classification_country_mismatch","country_id");
        Reject(()=>identity.RequireAssignable(country,Guid.NewGuid()),"tax_profile_classification_type_mismatch","tax_type_id");
        Reject(()=>(identity with {IsActive=false}).RequireAssignable(country,type),"tax_profile_classification_inactive");
        Reject(()=>(identity with {SupportedType=false}).RequireAssignable(country,type),"tax_classification_type_not_supported");
        identity.CheckMutation(5);count++;
        Reject(()=>identity.CheckMutation(4),"tax_classification_stale_version");
        Reject(()=>(identity with {SupportedType=false}).CheckMutation(5,true),"tax_classification_type_not_supported");
        // Lo stato della classificazione non entra nella risoluzione: i riferimenti inattivi restano storici.
        Assert(timeline.Resolve(country,type,from).ClassificationId==classifier,"historical resolution independent of classifier activation");
        JsonElement Json(string value)=>JsonDocument.Parse(value).RootElement.Clone();
        var values=JsonSerializer.SerializeToElement(new {country_id=country,tax_type_id=type,item_tax_classification_id=classifier,valid_from="2026-01-01",valid_to=(string?)null});
        var parsed=ClassificationInput.Profile(values,ClassificationKind.Item);
        Assert(parsed.ValidFrom==from && parsed.ValidTo==null && parsed.ClassificationId==classifier,"item payload accepted");
        Reject(()=>ClassificationInput.Profile(values,ClassificationKind.Partner),"tax_profile_invalid_payload");
        Reject(()=>ClassificationInput.Object(Json("{\"name\":\"a\",\"name\":\"b\"}"),"tax_classification","name"),"tax_classification_invalid_payload");
        Reject(()=>ClassificationInput.Object(Json("[]"),"tax_profile","values"),"tax_profile_invalid_payload");
        Reject(()=>ClassificationInput.Object(Json("{\"country_id\":null}"),"tax_classification","name","description"),"tax_classification_invalid_payload");
        foreach(var bad in new[]{"2025-02-29","2026-1-01","2026-01-01T00:00:00Z"," 2026-01-01",""}) Reject(()=>ClassificationInput.Date(bad,"valid_from"),"tax_profile_invalid_date","valid_from");
        foreach(var bad in new[]{"-1","9007199254740992","1.5","null","\"0\""}) {
            var raw=ClassificationInput.Object(Json("{\"expectedVersion\":"+bad+"}"),"tax_profile","expectedVersion");
            Reject(()=>ClassificationInput.Revision(raw,"tax_profile"),"tax_profile_invalid_expected_version","expectedVersion");
        }
        Reject(()=>ClassificationInput.Revision(ClassificationInput.Object(Json("{\"expectedVersion\":0}"),"tax_classification","expectedVersion"),"tax_classification"),"tax_classification_invalid_expected_version","expectedVersion");
        foreach(var version in new[]{0L,1L,ClassificationTimeline.MaxRevision}) Assert(ClassificationInput.Revision(ClassificationInput.Object(JsonSerializer.SerializeToElement(new {expectedVersion=version}),"tax_profile","expectedVersion"),"tax_profile")==version,"revision transport exact");
        foreach(var code in new[]{" X","X ","","a\u0000b"}) {
            var input=ClassificationInput.Object(JsonSerializer.SerializeToElement(new {code}),"tax_classification","code");
            try {ClassificationInput.Code(input);throw new Exception("Invalid code accepted");}catch(ApiException e) {Assert(e.Code.StartsWith("tax_classification_",StringComparison.Ordinal) && e.Field=="code","classification code error namespace and field");}
        }
        Reject(()=>ClassificationInput.Text(ClassificationInput.Object(Json("""{"name":"\uD800"}"""),"tax_classification","name"),"name",150,true),"tax_classification_invalid_field","name");
        Assert(ClassificationTemplates.Items.Length==10 && ClassificationTemplates.Items.Select(x=>x.Code).Distinct().Count()==10,"ten explicit item templates");
        Assert(ClassificationTemplates.Partners.Length==3 && ClassificationTemplates.Partners.Count(x=>x.Code=="UNKNOWN")==1,"three explicit partner templates");
        Assert(ClassificationKind.Parse("item")==ClassificationKind.Item && ClassificationKind.Parse("partner")==ClassificationKind.Partner,"finite discriminator");
        Reject(()=>ClassificationKind.Parse("item; DROP TABLE"),"tax_classification_invalid_kind","kind");
        Console.WriteLine($"Tax classification domain self-tests passed ({count} assertions).");
    }
}
