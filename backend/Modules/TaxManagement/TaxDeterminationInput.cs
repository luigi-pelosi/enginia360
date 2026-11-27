using System.Text.Json;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public sealed record TaxDeterminationRequest(Guid CompanyId,Guid BusinessPartnerId,Guid ItemId,Guid TaxTypeId,DateOnly TaxDate,string OperationType,Guid? CompanyTaxRegistrationId,Guid? PartnerTaxIdentifierId,IReadOnlyDictionary<string,JsonElement?> Fields,string? SourceReference,IReadOnlyList<Guid> DraftVersionIds);
public static class TaxDeterminationInput
{
    public static TaxDeterminationRequest Parse(JsonElement body,bool simulation)
    {
        string[] keys=["company_id","business_partner_id","item_id","tax_type_id","tax_date","operation_type","company_tax_registration_id","dispatch_country_id","destination_country_id","service_location_country_id","partner_tax_identifier_id","partner_acting_as_taxable_person","transaction_facts"];
        var o=Object(body,simulation?keys.Concat(new[]{"draft_version_ids"}).ToArray():keys);
        var operation=Text(o,"operation_type",8,true)!;Require(operation is "SALE" or "PURCHASE","tax_invalid_field",field:"operation_type");
        var f=new Dictionary<string,JsonElement?>(StringComparer.Ordinal){["transaction.operationType"]=JsonSerializer.SerializeToElement(operation)};
        void Reference(Dictionary<string,JsonElement> source,string input,string output){var id=Id(source,input);f[output]=id==null?null:JsonSerializer.SerializeToElement(id);}
        void Boolean(Dictionary<string,JsonElement> source,string input,string output){if(!source.TryGetValue(input,out var raw)||raw.ValueKind==JsonValueKind.Null){f[output]=null;return;}Require(raw.ValueKind is JsonValueKind.True or JsonValueKind.False,"tax_invalid_field",field:input);f[output]=raw.Clone();}
        void Enum(Dictionary<string,JsonElement> source,string input,string output,params string[] allowed){var s=Text(source,input,60);Require(s==null||allowed.Contains(s,StringComparer.Ordinal),"tax_invalid_field",field:input);f[output]=s==null?null:JsonSerializer.SerializeToElement(s);}
        Reference(o,"dispatch_country_id","transaction.dispatchCountry");Reference(o,"destination_country_id","transaction.destinationCountry");Reference(o,"service_location_country_id","transaction.serviceLocationCountry");Boolean(o,"partner_acting_as_taxable_person","partner.actingAsTaxablePerson");
        var facts=o.TryGetValue("transaction_facts",out var rawFacts)?Object(rawFacts,"operation_category","partner_establishment_country_id","ordinary_vat_territory_confirmed","special_tax_treatment","goods_location_country_id","goods_customs_status","source_reference"):new Dictionary<string,JsonElement>();
        Enum(facts,"operation_category","transaction.operationCategory","ORDINARY_MOVABLE_GOODS","GENERAL_SERVICES");Reference(facts,"partner_establishment_country_id","partner.establishmentCountry");Boolean(facts,"ordinary_vat_territory_confirmed","transaction.ordinaryVatTerritoryConfirmed");Enum(facts,"special_tax_treatment","transaction.specialTaxTreatment","NONE","REVERSE_CHARGE","SPLIT_PAYMENT","EXEMPT","MARGIN","OTHER");Reference(facts,"goods_location_country_id","transaction.goodsLocationCountry");Enum(facts,"goods_customs_status","transaction.goodsCustomsStatus","NATIONAL_OR_UNION","OTHER");
        var drafts=o.TryGetValue("draft_version_ids",out var raw)?Array(raw,"draft_version_ids",20).Select(x=>Id(new(){["draft_version_ids"]=x},"draft_version_ids",true)!.Value).ToArray():[];
        Require(drafts.Distinct().Count()==drafts.Length,"tax_duplicate_field",field:"draft_version_ids");
        return new(Id(o,"company_id",true)!.Value,Id(o,"business_partner_id",true)!.Value,Id(o,"item_id",true)!.Value,Id(o,"tax_type_id",true)!.Value,Date(o,"tax_date"),operation,Id(o,"company_tax_registration_id"),Id(o,"partner_tax_identifier_id"),f,Text(facts,"source_reference",255),drafts);
    }
}
