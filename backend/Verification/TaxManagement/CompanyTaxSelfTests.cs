using System.Text.Json;
using Enginia360.Modules.TaxManagement;
using Enginia360.Shared.Validation;
namespace Enginia360.Verification.TaxManagement;

public static class CompanyTaxSelfTests
{
    public static void Run()
    {
        var count=0;
        void Assert(bool ok,string label){if(!ok)throw new Exception("Company tax assertion failed: "+label);count++;}
        void Reject(Action action,string code,string? field=null){try{action();}catch(ApiException e) when(e.Code=="company_tax_"+code && (field==null || e.Field==field)){count++;return;}throw new Exception("Expected company_tax_"+code+" field="+field);}
        var tenant=Guid.NewGuid();var company=Guid.NewGuid();var country=Guid.NewGuid();var foreign=Guid.NewGuid();var type=Guid.NewGuid();var regimeId=Guid.NewGuid();var date=new DateOnly(2026,11,26);
        var regime=new CompanyTaxRegime(regimeId,country,type,"ORDINARY",true,true,date,null);
        Dictionary<Guid,CompanyTaxRegime> Regimes(CompanyTaxRegime? g=null)=>new(){[regimeId]=g??regime};
        CompanyTaxRegimeProfile P(DateOnly? start=null,DateOnly? end=null)=>new(Guid.NewGuid(),regimeId,start??date,end);
        CompanyTaxRegistration R(DateOnly? start=null,DateOnly? end=null,IReadOnlyList<CompanyTaxRegimeProfile>? profiles=null,Guid? nation=null,string number="IT12345678901",string kind="DOMESTIC")=>new(Guid.NewGuid(),nation??country,number,kind,start??date,end,null,profiles??[]);
        CompanyTaxConfiguration Root(IEnumerable<CompanyTaxRegistration>? children=null,string status="DRAFT",long version=1)=>new(Guid.NewGuid(),tenant,company,type,country,status,version,children);
        var root=Root();Assert(root.Status=="DRAFT" && root.Version==1,"draft revision one");Assert(root.Registrations.Count==0,"empty root");
        Reject(()=>new CompanyTaxConfiguration(Guid.Empty,tenant,company,type,country),"invalid_id");
        Reject(()=>Root(status:"DELETED"),"invalid_status");Reject(()=>Root(version:0),"invalid_version");
        Reject(()=>root.CheckVersion(0),"invalid_expected_version","expectedVersion");Reject(()=>root.CheckVersion(2),"stale_version","expectedVersion");
        Reject(()=>Root(version:TaxRules.MaxRevision).CheckVersion(TaxRules.MaxRevision),"version_exhausted");
        Reject(()=>root.SetStatus("ACTIVE",1,date,Regimes()),"activation_coverage_required");Assert(root.Version==1 && root.Status=="DRAFT","failed activation unchanged");
        var registration=R(profiles:[P()]);root.Initialize([registration],Regimes());
        var incomplete=Root();Reject(()=>incomplete.Initialize([],Regimes()),"initial_registration_required","registrations");
        Reject(()=>incomplete.Initialize([R()],Regimes()),"initial_regime_required","profiles");
        Reject(()=>incomplete.Initialize([registration,R()],Regimes()),"initial_regime_required","profiles");
        Assert(incomplete.Registrations.Count==0 && incomplete.Version==1,"missing initial chain leaves domain unchanged");
        Reject(()=>incomplete.Initialize([registration,R(profiles:[P()])],Regimes()),"identifier_overlap");
        Assert(incomplete.Registrations.Count==0 && incomplete.Version==1,"late initial validation failure leaves whole tree unchanged");
        var metadata=Root();Assert(metadata.TaxCode==null,"root tax code optional");
        metadata.UpdateTaxCode(" mixed CF / 李😀 ",1);
        Assert(metadata.TaxCode=="mixed CF / 李😀" && metadata.Version==2 && metadata.Status=="DRAFT","metadata trim without format or activation");
        Reject(()=>metadata.UpdateTaxCode("stale",1),"stale_version","expectedVersion");
        Reject(()=>metadata.UpdateTaxCode(new string('x',501),2),"field_too_long","tax_code");
        Assert(metadata.TaxCode=="mixed CF / 李😀" && metadata.Version==2,"failed metadata commands unchanged");
        metadata.UpdateTaxCode(null,2);Assert(metadata.TaxCode==null && metadata.Version==3,"explicit clear increments once");
        metadata.UpdateTaxCode("  \t\r\n",3);Assert(metadata.TaxCode==null && metadata.Version==4,"blank clears");
        Assert(root.Version==1 && root.Registrations.Count==1,"initial whole tree one revision");
        Reject(()=>root.Initialize([],Regimes()),"already_initialized");
        Assert(root.HasCoverage(date,Regimes()),"inclusive coverage start");Assert(root.HasCoverage(DateOnly.MaxValue,Regimes()),"open coverage end");Assert(!root.HasCoverage(date.AddDays(-1),Regimes()),"not before start");
        root.SetStatus("ACTIVE",1,date,Regimes());Assert(root.Version==2 && root.Status=="ACTIVE","activate advances exactly once");
        Reject(()=>root.SetStatus("ACTIVE",2,date,Regimes()),"invalid_transition");
        var context=root.Resolve(registration.Id,date,true,true,Regimes());Assert(context.TaxRegistrationId==registration.Id && context.TenantId==tenant,"explicit context identity");
        Assert(context.CompanyId==company && context.EstablishmentCountryId==country && context.TaxRegimeId==regimeId,"context chain");
        Reject(()=>root.Resolve(Guid.NewGuid(),date,false,true,Regimes()),"registration_not_found");
        Reject(()=>root.Resolve(registration.Id,date.AddDays(-1),false,true,Regimes()),"context_not_found","date");
        Reject(()=>root.Resolve(registration.Id,date,true,false,Regimes()),"not_eligible");
        Reject(()=>root.Close(registration.Id,date.AddDays(-1),2,date,Regimes()),"invalid_interval");
        Reject(()=>root.Close(registration.Id,date,1,date,Regimes()),"stale_version");
        root.Close(registration.Id,date,2,date,Regimes());Assert(root.Version==3,"close once for root and profiles");
        Assert(root.Registration(registration.Id).ValidTo==date && root.Registration(registration.Id).Profiles[0].ValidTo==date,"close clips crossing profile");
        Assert(root.Resolve(registration.Id,date,true,true,Regimes()).TaxDate==date,"inclusive closed end");
        Reject(()=>root.Resolve(registration.Id,date.AddDays(1),false,true,Regimes()),"context_not_found");
        Reject(()=>root.Close(registration.Id,date,3,date,Regimes()),"close_must_shorten");
        Reject(()=>root.Close(registration.Id,date.AddDays(1),3,date,Regimes()),"close_must_shorten");
        root.SetStatus("SUSPENDED",3,date,Regimes());Assert(root.Version==4,"suspend increments once");
        Assert(root.Resolve(registration.Id,date,false,false,Regimes()).TaxRegistrationId==registration.Id,"suspended disabled company historical");
        Reject(()=>root.Resolve(registration.Id,date,true,true,Regimes()),"not_eligible");
        Assert(root.Resolve(registration.Id,date,false,true,Regimes(regime with {IsActive=false,IsSupported=false})).TaxRegimeId==regimeId,"inactive unsupported regime historical");
        var active=Root([R(start:date.AddDays(-10),profiles:[P(date.AddDays(-10))])],"ACTIVE");var ar=active.Registrations[0];
        Reject(()=>active.Close(ar.Id,date.AddDays(-1),1,date,Regimes()),"active_coverage_required");Assert(active.Version==1 && active.Registration(ar.Id).ValidTo==null,"rejected close no domain mutation");
        var future=Root([R(profiles:[P(date.AddDays(10))])]);Reject(()=>future.Close(future.Registrations[0].Id,date.AddDays(5),1,date,Regimes()),"close_future_profile");
        var scheduling=Root([R(profiles:[P()])]);var sr=scheduling.Registrations[0];var successor=P(date.AddDays(10));
        Reject(()=>scheduling.AssignRegime(sr.Id,successor,1,false,date,Regimes()),"profile_overlap");
        scheduling.AssignRegime(sr.Id,successor,1,true,date,Regimes());
        Assert(scheduling.Version==2 && scheduling.Registration(sr.Id).Profiles.Count==2,"schedule advances once");
        Assert(scheduling.Registration(sr.Id).Profiles[0].ValidTo==date.AddDays(9),"predecessor inclusive day before");
        Assert(scheduling.Resolve(sr.Id,date.AddDays(9),false,true,Regimes()).TaxRegimeProfileId!=successor.Id,"previous day resolves predecessor");
        Assert(scheduling.Resolve(sr.Id,date.AddDays(10),false,true,Regimes()).TaxRegimeProfileId==successor.Id,"boundary resolves successor");
        Reject(()=>scheduling.AssignRegime(sr.Id,P(date.AddDays(5)),2,true,date,Regimes()),"profile_overlap");
        Reject(()=>Root().Initialize([R(profiles:[P(date.AddDays(-1))])],Regimes()),"profile_registration_validity_mismatch");
        Reject(()=>Root().Initialize([R(end:date.AddDays(5),profiles:[P()])],Regimes()),"profile_registration_validity_mismatch");
        Reject(()=>Root().Initialize([R(profiles:[P()])],Regimes(regime with {ValidFrom=date.AddDays(1)})),"profile_regime_validity_mismatch");
        Reject(()=>Root().Initialize([R(profiles:[P()])],Regimes(regime with {ValidTo=date.AddDays(10)})),"profile_regime_validity_mismatch");
        Reject(()=>Root().Initialize([R(profiles:[P()])],Regimes(regime with {CountryId=foreign})),"regime_scope_mismatch");
        Reject(()=>Root().Initialize([R(profiles:[P()])],Regimes(regime with {TaxTypeId=Guid.NewGuid()})),"regime_scope_mismatch");
        Reject(()=>Root().Initialize([R(profiles:[P()])],Regimes(regime with {IsActive=false})),"regime_not_supported");
        Reject(()=>Root().Initialize([R(profiles:[P()])],Regimes(regime with {IsSupported=false})),"regime_not_supported");
        Reject(()=>Root().Initialize([R(profiles:[P()])],Regimes(regime with {Code="SPECIAL"})),"regime_not_supported");
        Reject(()=>Root().Initialize([R(profiles:[P()])],new Dictionary<Guid,CompanyTaxRegime>()),"regime_not_found");
        Reject(()=>Root().Initialize([R(kind:"FOREIGN",profiles:[P()])],Regimes()),"invalid_registration_type");
        Reject(()=>Root().Initialize([R(kind:"DIRECT_IDENTIFICATION",profiles:[P()])],Regimes()),"registration_type_country_mismatch");
        Reject(()=>Root().Initialize([R(nation:foreign,profiles:[P()])],Regimes()),"registration_type_country_mismatch");
        Reject(()=>Root().Initialize([R(profiles:[P()]),R(number:"IT99999999999",profiles:[P()])],Regimes()),"domestic_overlap");
        Reject(()=>Root().Initialize([R(profiles:[P()]),R(profiles:[P()])],Regimes()),"identifier_overlap");
        var adjacent=Root();adjacent.Initialize([R(end:date,profiles:[P(end:date)]),R(start:date.AddDays(1),profiles:[P(date.AddDays(1))])],Regimes());Assert(adjacent.Registrations.Count==2,"adjacent registration periods allowed");
        var additional=Root([registration]);
        Reject(()=>additional.Register(R(nation:foreign,kind:"DIRECT_IDENTIFICATION"),1,date,Regimes()),"initial_regime_required","profiles");
        Assert(additional.Version==1 && additional.Status=="DRAFT" && additional.Registrations.SequenceEqual(new[]{registration}),"missing regime on additional registration leaves aggregate unchanged");
        var legacyRegistration=R();var legacy=Root([legacyRegistration]);
        Assert(legacy.Registration(legacyRegistration.Id).Profiles.Count==0,"legacy registration rehydrates without implicit regime");
        Reject(()=>legacy.Resolve(legacyRegistration.Id,date,false,true,Regimes()),"context_not_found","date");
        legacy.AssignRegime(legacyRegistration.Id,P(),1,false,date,Regimes());
        Assert(legacy.Version==2 && legacy.Resolve(legacyRegistration.Id,date,false,true,Regimes()).TaxRegimeId==regimeId,"legacy registration accepts later explicit assignment");
        var registering=Root();registering.Register(R(profiles:[P()]),1,date,Regimes());Assert(registering.Version==2 && registering.Status=="DRAFT","registration plus profiles one revision without activation");
        foreach(var status in new[]{"DRAFT","ACTIVE","SUSPENDED"}) {
            var existing=Root([registration],status,7);
            Reject(()=>existing.Register(R(nation:foreign,kind:"DIRECT_IDENTIFICATION"),7,date,Regimes()),"initial_regime_required","profiles");
            Assert(existing.Version==7 && existing.Status==status && existing.Registrations.SequenceEqual(new[]{registration}),"missing initial regime never mutates existing state");
        }
        Reject(()=>Root().Register(R(),1,date,Regimes()),"initial_regime_required","profiles");
        var atomicRegistration=Root();
        Reject(()=>atomicRegistration.Register(R(profiles:[P(end:date),P(date.AddDays(1))]),1,date,Regimes(regime with {ValidTo=date})),"profile_regime_validity_mismatch");
        Assert(atomicRegistration.Version==1 && atomicRegistration.Registrations.Count==0,"invalid second regime rejects entire registration");
        var temporal=Root();var temporalRegistration=R(profiles:[P(end:date),P(date.AddDays(1))]);
        temporal.Register(temporalRegistration,1,date,Regimes());
        Assert(temporal.Version==2 && temporal.Registrations[0].Profiles.Count==2,"multiple temporal initial profiles retained atomically");
        var delayed=Root();delayed.Register(R(profiles:[P(date.AddDays(10))]),1,date,Regimes());
        Assert(delayed.Version==2 && delayed.Status=="DRAFT" && !delayed.HasCoverage(date,Regimes()),"no new start-date or automatic activation policy");
        Assert(CompanyTaxJurisdiction.CanonicalIdentifier("IT","IT12345678901")=="IT12345678901","IT formal only no invented checksum");
        Assert(CompanyTaxJurisdiction.CanonicalIdentifier("DE","DE123456789")=="DE123456789","DE formal only");
        Assert(CompanyTaxJurisdiction.CanonicalIdentifier("FR","FRAB123456789")=="FRAB123456789","FR alphanumeric key");
        Assert(CompanyTaxJurisdiction.CanonicalIdentifier("FR","FR12123456789")=="FR12123456789","FR numeric key");
        foreach(var input in new[]{"it12345678901"," IT12345678901","IT12345678901 ","IT123 45678901","DE12345678901","12345678901","IT１２３４５６７８９０１","IT12345678901\0"})Reject(()=>CompanyTaxJurisdiction.CanonicalIdentifier("IT",input),"invalid_identifier");
        foreach(var input in new[]{"FRII123456789","FROO123456789","FRAB12345678","FRAB1234567890"})Reject(()=>CompanyTaxJurisdiction.CanonicalIdentifier("FR",input),"invalid_identifier");
        Reject(()=>CompanyTaxJurisdiction.CanonicalIdentifier("US","US123456789"),"country_not_supported");
        Assert(CompanyTaxJurisdiction.RegistrationTypes("IT","DE").Contains("FISCAL_REPRESENTATIVE"),"IT foreign representative supported");
        Assert(CompanyTaxJurisdiction.RegistrationTypes("FR","DE").SequenceEqual(new[]{"DIRECT_IDENTIFICATION"}),"foreign direct declarative policy");
        Reject(()=>CompanyTaxJurisdiction.RequireType("DE","IT","FISCAL_REPRESENTATIVE"),"registration_type_not_supported");
        Reject(()=>CompanyTaxJurisdiction.RequireType("FR","FR","DIRECT_IDENTIFICATION"),"registration_type_not_supported");
        Assert(CompanyTaxJurisdiction.RegistrationTypes("IT","IT").SequenceEqual(new[]{"DOMESTIC"}),"domestic only matching home");
        Assert(CompanyTaxJurisdiction.RegistrationTypes("US").Length==0,"unsupported country explicit");
        Assert(CompanyTaxJurisdiction.ValidationLevel("IT")=="FORMAT_ONLY","all supported formal-only");
        JsonElement Json(string json)=>JsonSerializer.Deserialize<JsonElement>(json);
        Reject(()=>CompanyTaxInput.Object(Json("{\"values\":{},\"values\":{}}"),"values"),"invalid_payload");
        Reject(()=>CompanyTaxInput.Object(Json("{\"arbitrary\":1}"),"values"),"invalid_payload");
        Reject(()=>CompanyTaxInput.Array(Json("{}"),"taxConfigurations"),"invalid_array","taxConfigurations");
        Reject(()=>CompanyTaxInput.Array(Json("null"),"taxConfigurations"),"invalid_array");
        Reject(()=>CompanyTaxInput.Version(CompanyTaxInput.Object(Json("{\"expectedVersion\":0}"),"expectedVersion")),"invalid_expected_version");
        Reject(()=>CompanyTaxInput.Date("2026-02-30","date"),"invalid_date","date");
        Reject(()=>CompanyTaxInput.Date("2026-1-01","date"),"invalid_date");
        Reject(()=>CompanyTaxInput.Text(CompanyTaxInput.Object(Json("{\"notes\":\"a\\u0000b\"}"),"notes"),"notes",100),"invalid_field","notes");
        Reject(()=>CompanyTaxInput.Text(CompanyTaxInput.Object(Json("{\"notes\":\"\\ud800\"}"),"notes"),"notes",100),"invalid_field","notes");
        var roleA=Guid.NewGuid();var roleB=Guid.NewGuid();
        Assert(!CompanyTaxAuthorization.ProjectPermissions([(roleA,"register")]).Contains("register"),"register alone cannot create a registration without assign authority");
        var split=CompanyTaxAuthorization.ProjectPermissions([(roleA,"register"),(roleB,"assign_regime")]);
        Assert(!split.Contains("register") && split.Contains("assign_regime"),"split roles cannot combine register and assign but later assign remains allowed");
        Assert(CompanyTaxAuthorization.ProjectPermissions([(roleA,"register"),(roleA,"assign_regime")]).Contains("register"),"same scoped role permits register with initial regime");
        Assert(CompanyTaxAuthorization.ProjectPermissions([(roleA,"read"),(roleB,"close")]).SequenceEqual(new[]{"read","close"}),"unrelated scoped actions unchanged");
        Assert(CompanyTaxAuthorization.ProjectPermissions([]).Length==0,"no scoped grants yields no actions");
        Assert(CompanyTaxAuthorization.Actions.Length==9 && CompanyTaxAuthorization.Actions.Contains("update"),"nine company scoped actions including metadata update");
        string Payload(object? registrations,bool include=true,object? taxCode=null)=>JsonSerializer.Serialize(new Dictionary<string,object?> {
            ["values"]=new {tax_type_id=type,establishment_country_id=country,tax_code=taxCode}
        }.Concat(include?new Dictionary<string,object?>{["registrations"]=registrations}:new Dictionary<string,object?>()).ToDictionary(x=>x.Key,x=>x.Value));
        var registrationValues=new {country_id=country,tax_identifier="IT12345678901",registration_type="DOMESTIC",valid_from="2026-11-26"};
        var initial=new[]{new {values=registrationValues,profiles=new[]{new {tax_regime_id=regimeId,valid_from="2026-11-26"}}}};
        Reject(()=>CompanyTaxInput.Create(Json(Payload(null,false))),"initial_registration_required","registrations");
        Reject(()=>CompanyTaxInput.Create(Json(Payload(Array.Empty<object>()))),"initial_registration_required","registrations");
        Reject(()=>CompanyTaxInput.Create(Json(Payload(null))),"invalid_array","registrations");
        Reject(()=>CompanyTaxInput.Create(Json(Payload(new[]{new {values=registrationValues}}))),"initial_regime_required","profiles");
        Reject(()=>CompanyTaxInput.Create(Json(Payload(new[]{new {values=registrationValues,profiles=Array.Empty<object>()}}))),"initial_regime_required","profiles");
        Reject(()=>CompanyTaxInput.Registration(Json(JsonSerializer.Serialize(new {values=registrationValues}))),"initial_regime_required","profiles");
        Reject(()=>CompanyTaxInput.Registration(Json(JsonSerializer.Serialize(new {values=registrationValues,profiles=Array.Empty<object>()}))),"initial_regime_required","profiles");
        foreach(var malformed in new object?[]{null,true,42,"bad",new {}})
            Reject(()=>CompanyTaxInput.Registration(Json(JsonSerializer.Serialize(new {values=registrationValues,profiles=malformed}))),"invalid_array","profiles");
        Assert(CompanyTaxInput.Registration(Json(JsonSerializer.Serialize(initial[0]))).Profiles.Count==1,"standalone registration accepts explicit initial regime");
        Assert(CompanyTaxInput.Create(Json(Payload(initial))).TaxCode==null,"create nullable tax code");
        foreach(var text in new[]{" mixed / CF 李😀 ",new string('x',500),string.Concat(Enumerable.Repeat("😀",250))})
            Assert(CompanyTaxInput.Create(Json(Payload(initial,taxCode:text))).TaxCode==text.Trim(),"create fiscal text preserves case and Unicode");
        foreach(var invalid in new object[]{42,true,new[]{"x"},new {value="x"},"bad\0value"})
            Reject(()=>CompanyTaxInput.Create(Json(Payload(initial,taxCode:invalid))),"invalid_field","tax_code");
        foreach(var invalid in new[]{new string('x',501),new string(' ',501)})
            Reject(()=>CompanyTaxInput.Create(Json(Payload(initial,taxCode:invalid))),"field_too_long","tax_code");
        Reject(()=>CompanyTaxInput.Update(Json("{\"values\":{},\"expectedVersion\":1}")),"field_required","tax_code");
        Reject(()=>CompanyTaxInput.Update(Json("{\"values\":{\"tax_code\":null,\"status\":\"ACTIVE\"},\"expectedVersion\":1}")),"invalid_payload");
        Reject(()=>CompanyTaxInput.Update(Json("{\"values\":{\"tax_code\":null,\"tax_code\":null},\"expectedVersion\":1}")),"invalid_payload");
        Reject(()=>CompanyTaxInput.Update(Json("{\"values\":{\"tax_code\":\"\\ud800\"},\"expectedVersion\":1}")),"invalid_field","tax_code");
        Assert(CompanyTaxInput.Update(Json("{\"values\":{\"tax_code\":null},\"expectedVersion\":7}")).ExpectedVersion==7,"update explicit clear and root token");
        Assert(CompanyTaxInput.Update(Json("{\"values\":{\"tax_code\":\"  \"},\"expectedVersion\":1}")).TaxCode==null,"update blank becomes null");
        Assert(CompanyTaxConfiguration.Covers(date,date,date),"single-day inclusive interval");
        Assert(!CompanyTaxConfiguration.Contains(date,date,date,null),"finite parent cannot contain unbounded child");
        Console.WriteLine($"Company tax domain self-tests passed: {count}");
    }
}
