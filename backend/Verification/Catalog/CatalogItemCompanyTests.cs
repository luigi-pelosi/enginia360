using System.Reflection;
using System.Text.Json;
using Enginia360.Modules.Catalog;
using Enginia360.Shared.Validation;

namespace Enginia360.Verification.Catalog;

public static class CatalogItemCompanyTests
{
    public static void Run(Action<string,Action> test)
    {
        void Ensure(bool valid) {if(!valid)throw new Exception("Company configuration invariant failed");}
        void Reject(string code,Action action) {
            try {action();}catch(ApiException e) {Ensure(e.Code==code);return;}
            throw new Exception("Expected "+code);
        }
        Dictionary<string,JsonElement> Input(string json)=>JsonSerializer.Deserialize<Dictionary<string,JsonElement>>(json)!;
        test("company defaults are copied once and nullable units remain fallback",()=>{
            var original=CatalogItemCompany.Defaults(true,false,true,"GOOD");
            var changedType=CatalogItemCompany.Defaults(false,true,false,"GOOD");
            Ensure(original.IsEnabled && original.IsSellable && !original.IsPurchasable && original.TrackStock);
            Ensure(original.DefaultSalesUomId==null && original.DefaultPurchaseUomId==null);
            Ensure(original!=changedType);
            Ensure(CatalogItemCompany.Merge(original,Input("{}"),"GOOD")==original);
        });
        test("company partial values preserve all omitted flags and allow explicit unit clear",()=>{
            var unit=Guid.NewGuid();
            var original=new CatalogItemCompany.Values(true,true,false,true,unit,unit);
            var merged=CatalogItemCompany.Merge(original,Input("{\"is_enabled\":false,\"default_sales_uom_id\":null}"),"GOOD");
            Ensure(!merged.IsEnabled && merged.IsSellable && !merged.IsPurchasable && merged.TrackStock);
            Ensure(merged.DefaultSalesUomId==null && merged.DefaultPurchaseUomId==unit);
            Ensure(original.IsEnabled && original.DefaultSalesUomId==unit);
        });
        test("all nonphysical natures reject stock in defaults and merged values",()=>{
            foreach(var kind in new[]{"INTANGIBLE","SERVICE","CHARGE"}) {
                Reject("nonphysical_cannot_track_stock",()=>CatalogItemCompany.Defaults(true,true,true,kind));
                var original=CatalogItemCompany.Defaults(true,true,false,kind);
                Reject("nonphysical_cannot_track_stock",()=>CatalogItemCompany.Merge(original,Input("{\"track_stock\":true}"),kind));
                Ensure(!CatalogItemCompany.Effective(original with {TrackStock=true},"ACTIVE",kind,true).CanTrackStock);
            }
        });
        test("company flags and units reject null booleans malformed UUID and coercion",()=>{
            var original=CatalogItemCompany.Defaults(true,true,false,"GOOD");
            foreach(var input in new[]{"{\"is_enabled\":null}","{\"is_sellable\":1}","{\"is_purchasable\":\"true\"}","{\"track_stock\":{}}"})
                Reject("invalid_field_value",()=>CatalogItemCompany.Merge(original,Input(input),"GOOD"));
            foreach(var raw in new[]{"\"not-a-uuid\"","123","\"00000000-0000-0000-0000-000000000000\"","\"{12345678-1234-1234-1234-123456789012}\""})
                Reject("invalid_company_item_unit",()=>CatalogItemCompany.Merge(original,Input("{\"default_sales_uom_id\":"+raw+"}"),"GOOD"));
        });
        test("archived items permit only unchanged payloads and disabling existing configurations",()=>{
            var before=CatalogItemCompany.Defaults(true,true,true,"GOOD");
            CatalogItemCompany.CheckMutable(before,before,"ARCHIVED",true);
            CatalogItemCompany.CheckMutable(before,before with {IsEnabled=false},"ARCHIVED",true);
            Reject("archived_item",()=>CatalogItemCompany.CheckMutable(null,before,"ARCHIVED",true));
            Reject("archived_item",()=>CatalogItemCompany.CheckMutable(before,before with {IsSellable=false},"ARCHIVED",true));
            Reject("archived_item",()=>CatalogItemCompany.CheckMutable(before with {IsEnabled=false},before,"ARCHIVED",true));
        });
        test("disabled companies allow reads noops and disable only never new configuration",()=>{
            var before=CatalogItemCompany.Defaults(true,true,true,"GOOD");
            CatalogItemCompany.CheckMutable(before,before,"SUSPENDED",false);
            CatalogItemCompany.CheckMutable(before,before with {IsEnabled=false},"ACTIVE",false);
            Reject("company_disabled",()=>CatalogItemCompany.CheckMutable(null,before,"ACTIVE",false));
            Reject("company_disabled",()=>CatalogItemCompany.CheckMutable(before,before with {IsPurchasable=false},"ACTIVE",false));
            CatalogItemCompany.CheckMutable(before,before with {IsPurchasable=false},"SUSPENDED",true);
        });
        test("effective operations require all active switches and independent configured flags",()=>{
            var before=CatalogItemCompany.Defaults(true,true,true,"GOOD");
            Ensure(CatalogItemCompany.Effective(before,"ACTIVE","GOOD",true)==(true,true,true));
            Ensure(CatalogItemCompany.Effective(before with {IsSellable=false},"ACTIVE","GOOD",true)==(false,true,true));
            Ensure(CatalogItemCompany.Effective(before with {IsPurchasable=false},"ACTIVE","GOOD",true)==(true,false,true));
            Ensure(CatalogItemCompany.Effective(before with {TrackStock=false},"ACTIVE","GOOD",true)==(true,true,false));
            foreach(var status in new[]{"SUSPENDED","ARCHIVED"})Ensure(CatalogItemCompany.Effective(before,status,"GOOD",true)==(false,false,false));
            Ensure(CatalogItemCompany.Effective(before,"ACTIVE","GOOD",false)==(false,false,false));
            Ensure(CatalogItemCompany.Effective(before with {IsEnabled=false},"ACTIVE","GOOD",true)==(false,false,false));
        });
        test("expected version never accepts stale retries including identical values",()=>{
            CatalogItemCompany.CheckVersion(0,0);
            CatalogItemCompany.CheckVersion(1,1);
            CatalogItemCompany.CheckVersion(CatalogItem.MaxVersion,CatalogItem.MaxVersion);
            Reject("stale_version",()=>CatalogItemCompany.CheckVersion(0,1));
            Reject("stale_version",()=>CatalogItemCompany.CheckVersion(1,2));
        });
        test("company configuration audit snapshot excludes metadata and uses exact allowlisted values",()=>{
            var before=CatalogItemCompany.Defaults(true,false,true,"GOOD");
            var snapshot=before.Snapshot();
            Ensure(snapshot.Count==CatalogItemCompany.Fields.Length);
            Ensure(snapshot.Keys.Order().SequenceEqual(CatalogItemCompany.Fields.Order()));
            Ensure((bool)snapshot["is_sellable"]! && !(bool)snapshot["is_purchasable"]! && snapshot["default_sales_uom_id"]==null);
        });
        test("company item stock policy supports only GOOD",()=>{
            var policy=typeof(CatalogItem).Assembly.GetType("Enginia360.Modules.Catalog.CatalogItemKind");
            if(policy==null) throw new Exception("Missing company item kind policy");
            var method=policy.GetMethod("SupportsStock",BindingFlags.Public|BindingFlags.Static)!;
            foreach(var kind in new[]{"GOOD","INTANGIBLE","SERVICE","CHARGE"})
                if((bool)method.Invoke(null,[kind])! != (kind=="GOOD")) throw new Exception("Unexpected stock eligibility");
        });
    }
}
