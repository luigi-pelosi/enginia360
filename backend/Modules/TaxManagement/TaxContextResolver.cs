using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public sealed record TaxContextResolution(TaxDeterminationContext Context,string? Outcome,IReadOnlyList<string> Issues);
/// <summary>Materializza solo fatti tipizzati e revisioni; nessun identificativo fiscale grezzo nella traccia.</summary>
public sealed class TaxContextResolver(AppDb db)
{
    public static async Task GateSources(HttpContext ctx,AppDb db,Guid tenant,Guid company,string action)
    {
        await TaxRuleReferences.Action(ctx,db,tenant,company,"tax-determination."+action);
        await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,company,"read");
        foreach(var permission in new[]{"catalog-items.read","business-partners.read","tax-item-profiles.read","tax-partner-profiles.read"})await Security.Authorize(ctx,permission);
    }
    public async Task<TaxContextResolution> Resolve(HttpContext ctx,Guid tenant,TaxDeterminationRequest request)
    {
        var italy=await db.Scalar("SELECT id FROM foundation.country WHERE iso_code='IT' AND is_enabled");Require(italy is Guid,"tax_country_not_found",404,"country_id");var country=(Guid)italy!;
        await TaxRuleReferences.RulesetLock(db,tenant,country,request.TaxTypeId,request.OperationType);
        await CompanyTaxApplication.Lock(db,tenant,false);
        // Stesso ordine globale dei writer: company, BP, item, configurazioni, classificazioni, regole, codici.
        var enabled=await CompanyTaxApplication.Company(db,tenant,request.CompanyId,false);
        Require(await db.Scalar("SELECT id FROM masterdata.business_partner WHERE tenant_id=@t AND id=@id FOR SHARE",("t",tenant),("id",request.BusinessPartnerId)) is Guid,"tax_partner_not_found",404,"business_partner_id");
        Require(await db.Scalar("SELECT id FROM masterdata.catalog_item WHERE tenant_id=@t AND id=@id FOR SHARE",("t",tenant),("id",request.ItemId)) is Guid,"tax_item_not_found",404,"item_id");
        foreach(var entry in new[]{(Kind:ClassificationKind.Item,Subject:request.ItemId),(Kind:ClassificationKind.Partner,Subject:request.BusinessPartnerId)}.OrderBy(x=>"tax-profile:"+x.Kind.Name+":"+tenant.ToString("D")+":"+x.Subject.ToString("D"),StringComparer.Ordinal))await TaxClassificationApplication.Lock(db,entry.Kind,tenant,entry.Subject,false);
        var partner=(await Rows(db,"SELECT id,version,status FROM masterdata.business_partner WHERE tenant_id=@t AND id=@id FOR SHARE",("t",tenant),("id",request.BusinessPartnerId))).SingleOrDefault()??throw new ApiException(404,"tax_partner_not_found","business_partner_id");
        var item=(await Rows(db,"SELECT i.id,i.version,i.status,i.item_type_id,t.kind,t.version AS type_version,t.is_active AS type_active FROM masterdata.catalog_item i JOIN masterdata.catalog_item_type t ON t.tenant_id=i.tenant_id AND t.id=i.item_type_id WHERE i.tenant_id=@t AND i.id=@id FOR SHARE OF i,t",("t",tenant),("id",request.ItemId))).SingleOrDefault()??throw new ApiException(404,"tax_item_not_found","item_id");
        var issues=new List<string>();var unsupported=false;
        void Unavailable(string issue){issues.Add(issue);unsupported=true;}
        if(!enabled)Unavailable("company_disabled");
        if((string)partner["status"]! != "ACTIVE")Unavailable("partner_unavailable");
        if((string)item["status"]! != "ACTIVE" || !(bool)item["type_active"]!)Unavailable("item_unavailable");
        var type=(await Rows(db,"SELECT code,is_active FROM taxmanagement.tax_types WHERE id=@id",("id",request.TaxTypeId))).SingleOrDefault()??throw new ApiException(404,"tax_type_not_found","tax_type_id");
        if((string)type["code"]! != "VAT" || !(bool)type["is_active"]!)Unavailable("type_not_supported");
        var fields=request.Fields.ToDictionary(x=>x.Key,x=>x.Value,StringComparer.Ordinal);
        void Set(string key,object? value)=>fields[key]=value==null?null:JsonSerializer.SerializeToElement(value);
        Set("item.nature",item["kind"]);Set("partner.vatValidationStatus",null);
        foreach(var entry in fields.Where(x=>x.Value?.ValueKind==JsonValueKind.String && (x.Key.EndsWith("Country",StringComparison.Ordinal))).ToArray()) {
            if(!Guid.TryParse(entry.Value!.Value.GetString(),out var id))continue;
            Require(await db.Scalar("SELECT id FROM foundation.country WHERE id=@id AND is_enabled",("id",id)) is Guid,"tax_country_not_found",404,entry.Key);
        }
        Guid? identifierCountry=null;
        var configuration=(await Rows(db,"SELECT id,version,status,establishment_country_id FROM taxmanagement.company_tax_configurations WHERE tenant_id=@t AND company_id=@c AND tax_type_id=@type ORDER BY id FOR SHARE",("t",tenant),("c",request.CompanyId),("type",request.TaxTypeId))).SingleOrDefault();
        if(configuration!=null && (string)configuration["status"]! != "ACTIVE")Unavailable("company_configuration_unavailable");
        if(configuration!=null && (Guid)configuration["establishment_country_id"]! != country)Unavailable("company_establishment_not_supported");
        if(request.PartnerTaxIdentifierId is Guid identifier){
            var row=(await Rows(db,"SELECT i.id,c.id AS country_id FROM masterdata.business_partner_tax_identifier i LEFT JOIN foundation.country c ON c.iso_code=i.country_code AND c.is_enabled WHERE i.tenant_id=@t AND i.business_partner_id=@bp AND i.id=@id",("t",tenant),("bp",request.BusinessPartnerId),("id",identifier))).SingleOrDefault()??throw new ApiException(404,"tax_partner_identifier_not_found","partner_tax_identifier_id");
            identifierCountry=row["country_id"] as Guid?;Require(identifierCountry!=null,"tax_country_not_found",404,"partner_tax_identifier_id");
        }
        Set("partner.taxIdentifierCountry",identifierCountry);
        CompanyTaxContext? companyContext=null;long? companyRevision=configuration?["version"] as long?;string selection="EXPLICIT";
        var resolver=new CompanyTaxProfileResolver(db);Guid? registration=request.CompanyTaxRegistrationId;
        if(registration==null){
            selection="UNIQUE_DOMESTIC_IT_ACTIVE_ORDINARY";
            // Solo il perimetro IT consente questa selezione applicativa, non il resolver Fase 3.
            var eligible=new List<CompanyTaxContext>();
            var eligibleRows=enabled?await resolver.List(tenant,request.CompanyId,request.TaxTypeId,request.TaxDate,true):System.Array.Empty<Dictionary<string,object?>>();
            foreach(var r in eligibleRows) {
                if((Guid)r["country_id"]! != country || (string)r["registration_type"]! != "DOMESTIC")continue;
                var resolved=await resolver.Resolve(tenant,request.CompanyId,(Guid)r["id"]!,request.TaxDate,true);
                if(resolved.EstablishmentCountryId==country && resolved.TaxRegimeCode=="ORDINARY")eligible.Add(resolved);
            }
            if(eligible.Count==1){companyContext=eligible[0];registration=companyContext.TaxRegistrationId;}
            else issues.Add(eligible.Count==0?"company_registration_missing":"company_registration_ambiguous");
        } else {
            try{companyContext=await resolver.Resolve(tenant,request.CompanyId,registration.Value,request.TaxDate,true);}
            catch(ApiException e) when(e.Code is "company_tax_context_not_found" or "company_tax_regime_not_supported" or "company_tax_not_eligible" or "company_tax_company_disabled" or "company_tax_configuration_not_active") {issues.Add(e.Code);}
            if(companyContext!=null)Require(companyContext.TaxTypeId==request.TaxTypeId,"tax_rule_invalid_reference",field:"company_tax_registration_id");
        }
        if(companyContext!=null){
            var root=await CompanyTaxApplication.Load(db,tenant,companyContext.ConfigurationId);companyRevision=root.Version;
            Set("company.taxRegime",companyContext.TaxRegimeId);Set("company.registrationCountry",companyContext.RegistrationCountryId);Set("company.establishmentCountry",companyContext.EstablishmentCountryId);
            if(companyContext.RegistrationType!="DOMESTIC"||companyContext.RegistrationCountryId!=country||companyContext.EstablishmentCountryId!=country||companyContext.TaxRegimeCode!="ORDINARY")Unavailable("company_context_not_supported");
        }else {Set("company.taxRegime",null);Set("company.registrationCountry",null);Set("company.establishmentCountry",null);}
        ITaxClassificationResolver classificationResolver=new TaxClassificationResolver(db);
        var profileSnapshots=new List<object>();
        foreach(var pair in new[]{(Kind:ClassificationKind.Item,Subject:request.ItemId,Field:"item.taxClassification"),(Kind:ClassificationKind.Partner,Subject:request.BusinessPartnerId,Field:"partner.taxClassification")}) {
            var streamRevision=await db.Scalar("SELECT coalesce(max(revision),0) FROM taxmanagement."+pair.Kind.ProfileTable+" WHERE tenant_id=@t AND "+pair.Kind.SubjectColumn+"=@id",("t",tenant),("id",pair.Subject));
            try{
                var p=pair.Kind.Name=="item"?await classificationResolver.ResolveItem(tenant,pair.Subject,country,request.TaxTypeId,request.TaxDate):await classificationResolver.ResolvePartner(tenant,pair.Subject,country,request.TaxTypeId,request.TaxDate);
                var classificationId=(Guid)p[pair.Kind.ClassificationColumn]!;
                var identity=await Classification(db,pair.Kind,tenant,classificationId);
                if(!(bool)identity["is_active"]!){Unavailable(pair.Kind.Name+"_classification_inactive");Set(pair.Field,null);}else Set(pair.Field,classificationId);
                profileSnapshots.Add(new {kind=pair.Kind.Name,profileId=p["id"],profileRevision=p["revision"],streamRevision,classificationId,classificationRevision=identity["version"]});
            }catch(ApiException e) when(e.Code=="tax_profile_not_found"){issues.Add(pair.Kind.Name+"_classification_missing");Set(pair.Field,null);profileSnapshots.Add(new{kind=pair.Kind.Name,streamRevision,profileId=(Guid?)null});}
        }
        var snapshot=JsonSerializer.SerializeToElement(new {company=new {id=request.CompanyId,configurationId=companyContext?.ConfigurationId??configuration?["id"] as Guid?,configurationRevision=companyRevision,configurationStatus=configuration?["status"],registrationId=registration,regimeProfileId=companyContext?.TaxRegimeProfileId,selection},partner=new{id=request.BusinessPartnerId,version=partner["version"],identifierId=request.PartnerTaxIdentifierId,identifierCountryId=identifierCountry,identifierTemporal=false,vatValidationStatus="UNKNOWN"},item=new{id=request.ItemId,version=item["version"],typeId=item["item_type_id"],typeRevision=item["type_version"]},profiles=profileSnapshots,facts=new{source="INPUT",sourceReference=request.SourceReference,fields=request.Fields},issues});
        var context=new TaxDeterminationContext {TenantId=tenant,CompanyId=request.CompanyId,BusinessPartnerId=request.BusinessPartnerId,ItemId=request.ItemId,TaxTypeId=request.TaxTypeId,ItalyCountryId=country,TaxDate=request.TaxDate,OperationType=request.OperationType,TaxTypeCode=(string)type["code"]!,ItemKind=(string)item["kind"]!,CompanyRegimeCode=companyContext?.TaxRegimeCode??"",CompanyTaxRegistrationId=registration,Fields=fields,Snapshot=snapshot};
        return new(context,issues.Count==0?null:unsupported?"UNSUPPORTED_OPERATION":"INCOMPLETE_CONTEXT",issues);
    }
}
