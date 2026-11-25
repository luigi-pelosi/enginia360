using System.Text.Json;
using Enginia360.Modules.Catalog;
using Enginia360.Shared.Validation;

namespace Enginia360.Verification.Catalog;

public static class CatalogItemCompanyCreationTests
{
    public static void Run(Action<string,Action> test)
    {
        void Ensure(bool valid) {if(!valid)throw new Exception("Atomic company creation invariant failed");}
        JsonElement Json(string text)=>JsonSerializer.Deserialize<JsonElement>(text);
        void Reject(string text) {
            try {CatalogItemCompanyEndpoints.ParseCreationCompanies(Json(text));}
            catch(ApiException e) {Ensure(e.Status==400);return;}
            throw new Exception("Expected invalid company creation payload");
        }
        var company=Guid.NewGuid();
        string Row(Guid id,string values="{}")=>"{\"company_id\":\""+id+"\",\"values\":"+values+"}";
        test("atomic company creation permits empty explicit opt-in",()=>{
            Ensure(CatalogItemCompanyEndpoints.ParseCreationCompanies(Json("[]")).Length==0);
        });
        test("atomic company creation parses only company identity and explicit values",()=>{
            var rows=CatalogItemCompanyEndpoints.ParseCreationCompanies(Json("["+Row(company)+"]"));
            Ensure(rows.Length==1 && rows[0].Company==company && rows[0].Values.Count==0);
        });
        test("atomic company creation rejects malformed arrays and company identities",()=>{
            foreach(var text in new[]{"null","{}","[null]","[{}]","[{\"company_id\":null,\"values\":{}}]","[{\"company_id\":42,\"values\":{}}]","[{\"company_id\":\"bad\",\"values\":{}}]","["+Row(Guid.Empty)+"]"})Reject(text);
        });
        test("atomic company creation requires object values and rejects unknown fields",()=>{
            Reject("[{\"company_id\":\""+company+"\"}]");
            Reject("["+Row(company,"null")+"]");
            Reject("["+Row(company,"{\"canSell\":true}")+"]");
            Reject("[{\"company_id\":\""+company+"\",\"values\":{},\"expectedVersion\":0}]");
            Reject("[{\"company_id\":\""+company+"\",\"company_id\":\""+Guid.NewGuid()+"\",\"values\":{}}]");
        });
        test("atomic company creation rejects duplicate UUIDs including alternate case",()=>{
            Reject("["+Row(company)+","+Row(company)+"]");
            Reject("["+Row(company)+","+Row(company).ToUpperInvariant().Replace("COMPANY_ID","company_id").Replace("VALUES","values")+"]");
        });
        test("atomic company creation is bounded to one hundred unique companies",()=>{
            var rows=Enumerable.Range(0,100).Select(_=>Row(Guid.NewGuid())).ToArray();
            Ensure(CatalogItemCompanyEndpoints.ParseCreationCompanies(Json("["+string.Join(',',rows)+"]")).Length==100);
            Reject("["+string.Join(',',rows.Append(Row(Guid.NewGuid())))+"]");
        });
        test("atomic company values override a snapshot of selected type defaults",()=>{
            var unit=Guid.NewGuid();
            var rows=CatalogItemCompanyEndpoints.ParseCreationCompanies(Json("["+Row(company,"{\"is_sellable\":false,\"default_sales_uom_id\":\""+unit+"\",\"default_purchase_uom_id\":null}")+"]"));
            var defaults=CatalogItemCompany.Defaults(true,false,true,"GOOD");
            var merged=CatalogItemCompany.Merge(defaults,rows[0].Values,"GOOD");
            Ensure(!merged.IsSellable && !merged.IsPurchasable && merged.TrackStock && merged.IsEnabled);
            Ensure(merged.DefaultSalesUomId==unit && merged.DefaultPurchaseUomId==null);
            Ensure(defaults.IsSellable && defaults.DefaultSalesUomId==null);
        });
    }
}
