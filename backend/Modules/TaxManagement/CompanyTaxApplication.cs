using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Npgsql;
using static Enginia360.Modules.TaxManagement.CompanyTaxConfiguration;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
namespace Enginia360.Modules.TaxManagement;

public static class CompanyTaxApplication
{
    public static DateOnly Today=>DateOnly.FromDateTime(DateTime.UtcNow);
    public static Task Lock(AppDb db,Guid tenant,bool write)=>db.Execute("SELECT "+(write?"pg_advisory_xact_lock":"pg_advisory_xact_lock_shared")+"(hashtextextended(@k,0))",("k","company-tax:"+tenant));
    public static async Task<bool> Company(AppDb db,Guid tenant,Guid company,bool write)
    {
        var enabled=await db.Scalar("SELECT is_enabled FROM foundation.company WHERE tenant_id=@t AND id=@c FOR SHARE",("t",tenant),("c",company));
        Require(enabled is bool,"company_not_found",404,"companyId");Require(!write || (bool)enabled!,"company_disabled",409,"companyId");return (bool)enabled!;
    }
    public static async Task Actor(HttpContext ctx,AppDb db,Guid tenant)
    {
        Require(await db.Scalar("SELECT id FROM foundation.\"user\" WHERE id=@u AND is_enabled AND ((tenant_id=@t AND NOT is_super_admin) OR (tenant_id IS NULL AND is_super_admin))",("u",Security.State(ctx).User.Id),("t",tenant)) is Guid,"invalid_actor",403);
    }
    public static async Task<Dictionary<Guid,CompanyTaxRegime>> Regimes(AppDb db)
    {
        var rows=await Rows(db,"SELECT g.id,g.country_id,g.tax_type_id,g.code,(g.is_active AND c.is_enabled AND t.is_active AND t.code='VAT') AS is_active,(g.is_supported AND c.iso_code IN ('IT','DE','FR')) AS is_supported,g.valid_from,g.valid_to FROM taxmanagement.tax_regimes g JOIN foundation.country c ON c.id=g.country_id JOIN taxmanagement.tax_types t ON t.id=g.tax_type_id ORDER BY g.id LIMIT 10001");Require(rows.Count<=10000,"lookup_limit_exceeded",409);
        return rows.ToDictionary(r=>(Guid)r["id"]!,r=>new CompanyTaxRegime((Guid)r["id"]!,(Guid)r["country_id"]!,(Guid)r["tax_type_id"]!,(string)r["code"]!,(bool)r["is_active"]!,(bool)r["is_supported"]!,(DateOnly)r["valid_from"]!,r["valid_to"] as DateOnly?));
    }
    public static CompanyTaxRegimeProfile Profile(Dictionary<string,object?> r)=>new((Guid)r["id"]!,(Guid)r["tax_regime_id"]!,(DateOnly)r["valid_from"]!,r["valid_to"] as DateOnly?);
    public static async Task<CompanyTaxConfiguration> Load(AppDb db,Guid tenant,Guid id,bool write=false)
    {
        var r=(await Rows(db,"SELECT * FROM taxmanagement.company_tax_configurations WHERE tenant_id=@t AND id=@id"+(write?" FOR UPDATE":" FOR SHARE"),("t",tenant),("id",id))).SingleOrDefault()??throw new ApiException(404,"company_tax_configuration_not_found","id");
        var registrations=await Rows(db,"SELECT * FROM taxmanagement.company_tax_registrations WHERE tenant_id=@t AND company_tax_configuration_id=@id ORDER BY valid_from,id",("t",tenant),("id",id));
        var profiles=await Rows(db,"SELECT p.* FROM taxmanagement.company_tax_regime_profiles p JOIN taxmanagement.company_tax_registrations r ON r.tenant_id=p.tenant_id AND r.id=p.company_tax_registration_id WHERE r.tenant_id=@t AND r.company_tax_configuration_id=@id ORDER BY p.valid_from,p.id",("t",tenant),("id",id));
        return new((Guid)r["id"]!,tenant,(Guid)r["company_id"]!,(Guid)r["tax_type_id"]!,(Guid)r["establishment_country_id"]!,(string)r["status"]!,(long)r["version"]!,registrations.Select(x=>new CompanyTaxRegistration((Guid)x["id"]!,(Guid)x["country_id"]!,(string)x["tax_identifier"]!,(string)x["registration_type"]!,(DateOnly)x["valid_from"]!,x["valid_to"] as DateOnly?,x["notes"] as string,profiles.Where(p=>(Guid)p["company_tax_registration_id"]! == (Guid)x["id"]!).Select(Profile).ToArray())),r["tax_code"] as string);
    }
    public static async Task<Dictionary<string,object?>> Read(AppDb db,Guid tenant,Guid id)
    {
        var root=(await Rows(db,"SELECT * FROM taxmanagement.company_tax_configurations WHERE tenant_id=@t AND id=@id",("t",tenant),("id",id))).SingleOrDefault()??throw new ApiException(404,"company_tax_configuration_not_found","id");
        var registrations=await Rows(db,"SELECT r.*,c.iso_code AS country_iso_code FROM taxmanagement.company_tax_registrations r JOIN foundation.country c ON c.id=r.country_id WHERE r.tenant_id=@t AND r.company_tax_configuration_id=@id ORDER BY r.valid_from,r.id",("t",tenant),("id",id));
        var profiles=await Rows(db,"SELECT p.*,g.code AS tax_regime_code,g.name AS tax_regime_name,g.is_active AS tax_regime_is_active,g.is_supported AS tax_regime_is_supported FROM taxmanagement.company_tax_regime_profiles p JOIN taxmanagement.company_tax_registrations r ON r.tenant_id=p.tenant_id AND r.id=p.company_tax_registration_id JOIN taxmanagement.tax_regimes g ON g.id=p.tax_regime_id WHERE r.tenant_id=@t AND r.company_tax_configuration_id=@id ORDER BY p.valid_from,p.id",("t",tenant),("id",id));
        foreach(var r in registrations)r["profiles"]=profiles.Where(p=>(Guid)p["company_tax_registration_id"]! == (Guid)r["id"]!).ToArray();root["registrations"]=registrations;return root;
    }
    public static async Task<string> Country(AppDb db,Guid id)
    {
        var iso=await db.Scalar("SELECT iso_code FROM foundation.country WHERE id=@id AND is_enabled",("id",id)) as string;
        Require(iso!=null,"invalid_country",field:"country_id");return iso!;
    }
    public static async Task Scope(AppDb db,Guid type,Guid establishment)
    {
        Require(await db.Scalar("SELECT id FROM taxmanagement.tax_types WHERE id=@id AND code='VAT' AND is_active",("id",type)) is Guid,"type_not_supported",field:"tax_type_id");
        var establishmentIso=await Country(db,establishment);
        Require(CompanyTaxJurisdiction.SupportedCountries.Contains(establishmentIso,StringComparer.Ordinal),"establishment_country_not_supported",field:"establishment_country_id");
    }
    private static async Task<CompanyTaxRegistration> Prepare(AppDb db,CompanyTaxConfiguration root,CompanyTaxRegistrationInput input)
    {
        var iso=await Country(db,input.CountryId);var establishment=await Country(db,root.EstablishmentCountryId);
        CompanyTaxJurisdiction.RequireType(iso,establishment,input.RegistrationType);
        var identifier=CompanyTaxJurisdiction.CanonicalIdentifier(iso,input.TaxIdentifier);
        // Il lock tenant serializza anche le identità uguali su aziende differenti.
        var duplicate=await db.Scalar("SELECT r.id FROM taxmanagement.company_tax_registrations r JOIN taxmanagement.company_tax_configurations c ON c.tenant_id=r.tenant_id AND c.id=r.company_tax_configuration_id WHERE r.tenant_id=@t AND c.tax_type_id=@type AND r.country_id=@country AND r.tax_identifier=@number AND r.valid_from<=coalesce(@end::date,'infinity'::date) AND coalesce(r.valid_to,'infinity'::date)>=@start LIMIT 1",("t",root.TenantId),("type",root.TaxTypeId),("country",input.CountryId),("number",identifier),("start",input.ValidFrom),("end",input.ValidTo));
        Require(duplicate==null,"identifier_overlap",409,"tax_identifier");
        return new(Guid.NewGuid(),input.CountryId,identifier,input.RegistrationType,input.ValidFrom,input.ValidTo,input.Notes,input.Profiles);
    }
    public static async Task<Dictionary<string,object?>> Create(HttpContext ctx,AppDb db,Guid tenant,Guid company,CompanyTaxCreateInput input,bool initial=false)
    {
        Require(input.Registrations.Count>0,"initial_registration_required",field:"registrations");
        Require(input.Registrations.All(r=>r.Profiles.Count>0),"initial_regime_required",field:"profiles");
        await Actor(ctx,db,tenant);await Company(db,tenant,company,true);await Lock(db,tenant,true);
        await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,company,"create");
        await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,company,"register");
        await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,company,"assign_regime");
        await Scope(db,input.TaxTypeId,input.EstablishmentCountryId);
        var root=new CompanyTaxConfiguration(Guid.NewGuid(),tenant,company,input.TaxTypeId,input.EstablishmentCountryId,taxCode:input.TaxCode);
        var children=new List<CompanyTaxRegistration>();foreach(var r in input.Registrations)children.Add(await Prepare(db,root,r));
        root.Initialize(children,await Regimes(db));
        try {
            await db.Execute("INSERT INTO taxmanagement.company_tax_configurations(id,tenant_id,company_id,tax_type_id,establishment_country_id,tax_code,status,version,created_at,updated_at,created_by) VALUES(@id,@t,@c,@type,@est,@taxCode::text,'DRAFT',1,clock_timestamp(),clock_timestamp(),@actor)",("id",root.Id),("t",tenant),("c",company),("type",input.TaxTypeId),("est",input.EstablishmentCountryId),("taxCode",root.TaxCode),("actor",Security.State(ctx).User.Id));
            await SaveChildren(ctx,db,root,[]);
        }catch(PostgresException e) when(e.SqlState is "23505" or "23P01"){throw Conflict(e);}
        await Audit(ctx,db,root,initial?"initial_create":"create",null);
        return await Read(db,tenant,root.Id);
    }
    private static ApiException Conflict(PostgresException e)=>new(409,e.SqlState=="23P01"?"company_tax_overlap":"company_tax_configuration_exists","values");
    private static async Task SaveChildren(HttpContext ctx,AppDb db,CompanyTaxConfiguration root,IReadOnlyList<CompanyTaxRegistration> before)
    {
        var actor=Security.State(ctx).User.Id;
        foreach(var r in root.Registrations) {
            var old=before.SingleOrDefault(x=>x.Id==r.Id);
            if(old==null)await db.Execute("INSERT INTO taxmanagement.company_tax_registrations(id,tenant_id,company_tax_configuration_id,country_id,tax_identifier,registration_type,valid_from,valid_to,notes,created_at,created_by) VALUES(@id,@t,@root,@country,@number,@kind,@from,@to::date,@notes::text,clock_timestamp(),@actor)",("id",r.Id),("t",root.TenantId),("root",root.Id),("country",r.CountryId),("number",r.TaxIdentifier),("kind",r.RegistrationType),("from",r.ValidFrom),("to",r.ValidTo),("notes",r.Notes),("actor",actor));
            else if(old.ValidTo!=r.ValidTo)await db.Execute("UPDATE taxmanagement.company_tax_registrations SET valid_to=@to::date WHERE tenant_id=@t AND id=@id",("to",r.ValidTo),("t",root.TenantId),("id",r.Id));
            foreach(var p in r.Profiles) {
                var previous=old?.Profiles.SingleOrDefault(x=>x.Id==p.Id);
                if(previous==null)await db.Execute("INSERT INTO taxmanagement.company_tax_regime_profiles(id,tenant_id,company_tax_registration_id,tax_regime_id,valid_from,valid_to,created_at,created_by) VALUES(@id,@t,@registration,@regime,@from,@to::date,clock_timestamp(),@actor)",("id",p.Id),("t",root.TenantId),("registration",r.Id),("regime",p.TaxRegimeId),("from",p.ValidFrom),("to",p.ValidTo),("actor",actor));
                else if(previous.ValidTo!=p.ValidTo)await db.Execute("UPDATE taxmanagement.company_tax_regime_profiles SET valid_to=@to::date WHERE tenant_id=@t AND id=@id",("to",p.ValidTo),("t",root.TenantId),("id",p.Id));
            }
        }
    }
    private static Task Audit(HttpContext ctx,AppDb db,CompanyTaxConfiguration root,string action,long? oldVersion)=>db.Audit(Security.State(ctx).User.Id,root.TenantId,action,CompanyTaxAuthorization.Resource,root.Id,new {company_id=root.CompanyId,tax_type_id=root.TaxTypeId,tax_code=root.TaxCode,before_version=oldVersion,version=root.Version,status=root.Status,registration_ids=root.Registrations.Select(r=>r.Id).ToArray(),profile_ids=root.Registrations.SelectMany(r=>r.Profiles).Select(p=>p.Id).ToArray()});
    public static async Task<Dictionary<string,object?>> Mutate(HttpContext ctx,AppDb db,Guid tenant,Guid id,string action,long expected,Guid? registrationId=null,CompanyTaxRegistrationInput? registration=null,CompanyTaxRegimeProfile? profile=null,DateOnly? end=null,string? taxCode=null)
    {
        await Lock(db,tenant,true);var root=await Load(db,tenant,id,true);
        await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,root.CompanyId,action);
        await Company(db,tenant,root.CompanyId,true);await Actor(ctx,db,tenant);
        if(action is not "suspend" and not "close" and not "update")await Scope(db,root.TaxTypeId,root.EstablishmentCountryId);
        root.CheckVersion(expected);var before=root.Registrations.ToArray();var oldVersion=root.Version;var regimes=await Regimes(db);
        switch(action) {
            case "update":root.UpdateTaxCode(taxCode,expected);break;
            case "activate":root.SetStatus("ACTIVE",expected,Today,regimes);break;
            case "suspend":root.SetStatus("SUSPENDED",expected,Today,regimes);break;
            case "register":
                await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,root.CompanyId,"assign_regime");
                root.Register(await Prepare(db,root,registration!),expected,Today,regimes);break;
            case "close":root.Close(registrationId!.Value,end!.Value,expected,Today,regimes);break;
            case "assign_regime":case "schedule_regime":root.AssignRegime(registrationId!.Value,profile!,expected,action=="schedule_regime",Today,regimes);break;
            default:throw new ApiException(400,"company_tax_invalid_action");
        }
        try {
            await SaveChildren(ctx,db,root,before);
            var changed=await db.Execute("UPDATE taxmanagement.company_tax_configurations SET status=@status,tax_code=@taxCode::text,version=@version,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id AND version=@old",("status",root.Status),("taxCode",root.TaxCode),("version",root.Version),("t",tenant),("id",id),("old",oldVersion));
            Require(changed==1,"stale_version",409,"expectedVersion");
        }catch(PostgresException e) when(e.SqlState is "23505" or "23P01"){throw Conflict(e);}
        await Audit(ctx,db,root,action,oldVersion);return await Read(db,tenant,id);
    }
    public static async Task AssignInitial(HttpContext ctx,AppDb db,Guid tenant,Guid company,JsonElement raw)
    {
        var entries=CompanyTaxInput.Array(raw,"taxConfigurations",20);
        if(entries.Length==0)return;
        // Nessuna delega implicita: role_company non esiste ancora per la nuova azienda.
        Require(CompanyTaxAuthorization.Global(Security.State(ctx)),"initial_global_required",403,"taxConfigurations");
        var authorized=await CompanyTaxAuthorization.Tenant(ctx,db);Require(authorized==tenant,"tenant_mismatch",403,"tenantId");
        var inputs=entries.Select(CompanyTaxInput.Create).ToArray();
        Require(inputs.Select(x=>x.TaxTypeId).Distinct().Count()==inputs.Length,"duplicate_configuration",field:"taxConfigurations");
        foreach(var input in inputs)await Create(ctx,db,tenant,company,input,true);
    }
}

/// <summary>Elenco esplicito e risoluzione puntuale; nessuna selezione automatica della registrazione.</summary>
public sealed class CompanyTaxProfileResolver(AppDb db)
{
    public async Task<IReadOnlyList<Dictionary<string,object?>>> List(Guid tenant,Guid company,Guid? taxType,DateOnly date,bool forNewUse=false)
    {
        await CompanyTaxApplication.Lock(db,tenant,false);var enabled=await CompanyTaxApplication.Company(db,tenant,company,false);
        Require(!forNewUse || enabled,"company_disabled",409,"companyId");
        var roots=await TaxClassificationApplication.Rows(db,"SELECT id FROM taxmanagement.company_tax_configurations WHERE tenant_id=@t AND company_id=@c AND (@type::uuid IS NULL OR tax_type_id=@type) ORDER BY id",("t",tenant),("c",company),("type",taxType));
        var result=new List<Dictionary<string,object?>>();var regimes=await CompanyTaxApplication.Regimes(db);
        foreach(var row in roots) {
            var root=await CompanyTaxApplication.Load(db,tenant,(Guid)row["id"]!);
            if(forNewUse && root.Status!="ACTIVE")continue;
            foreach(var r in root.Registrations) {
                try {
                    _=root.Resolve(r.Id,date,forNewUse,enabled,regimes);
                    if(forNewUse && !await EligibleCatalog(root,r))continue;
                    result.Add(new(){["id"]=r.Id,["company_tax_configuration_id"]=root.Id,["country_id"]=r.CountryId,["tax_type_id"]=root.TaxTypeId,["tax_identifier"]=r.TaxIdentifier,["registration_type"]=r.RegistrationType,["valid_from"]=r.ValidFrom,["valid_to"]=r.ValidTo,["configuration_status"]=root.Status});
                }catch(ApiException e) when(e.Code is "company_tax_context_not_found" or "company_tax_regime_not_supported"){}
            }
        }
        return result;
    }
    private async Task<bool> EligibleCatalog(CompanyTaxConfiguration root,CompanyTaxRegistration r)=>await db.Scalar("SELECT EXISTS(SELECT 1 FROM taxmanagement.tax_types t JOIN foundation.country c ON c.id=@country JOIN foundation.country e ON e.id=@est WHERE t.id=@type AND t.code='VAT' AND t.is_active AND c.is_enabled AND e.is_enabled)",("country",r.CountryId),("est",root.EstablishmentCountryId),("type",root.TaxTypeId)) is true;
    public async Task<CompanyTaxContext> Resolve(Guid tenant,Guid company,Guid registrationId,DateOnly date,bool forNewUse=false)
    {
        await CompanyTaxApplication.Lock(db,tenant,false);var enabled=await CompanyTaxApplication.Company(db,tenant,company,false);
        var id=await db.Scalar("SELECT c.id FROM taxmanagement.company_tax_configurations c JOIN taxmanagement.company_tax_registrations r ON r.tenant_id=c.tenant_id AND r.company_tax_configuration_id=c.id WHERE c.tenant_id=@t AND c.company_id=@c AND r.id=@id",("t",tenant),("c",company),("id",registrationId));
        Require(id is Guid,"registration_not_found",404,"registrationId");var root=await CompanyTaxApplication.Load(db,tenant,(Guid)id!);
        var result=root.Resolve(registrationId,date,forNewUse,enabled,await CompanyTaxApplication.Regimes(db));
        Require(!forNewUse || await EligibleCatalog(root,root.Registration(registrationId)),"not_eligible",409,"date");return result;
    }
}
