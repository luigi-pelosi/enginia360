using System.Text.Json;
using static Enginia360.Modules.Catalog.CatalogItem;

namespace Enginia360.Modules.Catalog;

// Configurazione autonoma: nessuna revisione o propagazione dei default sull'articolo.
public static class CatalogItemCompany
{
    public static readonly string[] Fields=["is_enabled","is_sellable","is_purchasable","track_stock","default_sales_uom_id","default_purchase_uom_id"];
    public sealed record Values(bool IsEnabled,bool IsSellable,bool IsPurchasable,bool TrackStock,Guid? DefaultSalesUomId,Guid? DefaultPurchaseUomId)
    {
        public Dictionary<string,object?> Snapshot()=>new() {
            ["is_enabled"]=IsEnabled,["is_sellable"]=IsSellable,["is_purchasable"]=IsPurchasable,["track_stock"]=TrackStock,
            ["default_sales_uom_id"]=DefaultSalesUomId,["default_purchase_uom_id"]=DefaultPurchaseUomId
        };
    }
    public static Values Defaults(bool sellable,bool purchasable,bool stock,string kind)
    {
        Require(!stock || CatalogItemKind.SupportsStock(kind),400,"nonphysical_cannot_track_stock","track_stock");
        return new(true,sellable,purchasable,stock,null,null);
    }
    public static Values Merge(Values before,Dictionary<string,JsonElement> input,string kind)
    {
        bool Flag(string key,bool old) {
            if(!input.TryGetValue(key,out var v)) return old;
            Require(v.ValueKind is JsonValueKind.True or JsonValueKind.False,400,"invalid_field_value",key);
            return v.GetBoolean();
        }
        Guid? Unit(string key,Guid? old) {
            if(!input.TryGetValue(key,out var v))return old;
            if(v.ValueKind==JsonValueKind.Null)return null;
            Require(v.ValueKind==JsonValueKind.String,400,"invalid_company_item_unit",key);
            string? text;
            try {text=v.GetString();} catch(InvalidOperationException) {throw new Enginia360.Shared.Validation.ApiException(400,"invalid_company_item_unit",key);}
            Require(Guid.TryParseExact(text,"D",out var id) && id!=Guid.Empty,400,"invalid_company_item_unit",key);
            return id;
        }
        var result=new Values(Flag("is_enabled",before.IsEnabled),Flag("is_sellable",before.IsSellable),Flag("is_purchasable",before.IsPurchasable),Flag("track_stock",before.TrackStock),Unit("default_sales_uom_id",before.DefaultSalesUomId),Unit("default_purchase_uom_id",before.DefaultPurchaseUomId));
        Require(!result.TrackStock || CatalogItemKind.SupportsStock(kind),400,"nonphysical_cannot_track_stock","track_stock");
        return result;
    }
    public static void CheckVersion(long expected,long actual)=>Require(expected==actual,409,"stale_version");
    public static void CheckMutable(Values? before,Values after,string status,bool companyEnabled)
    {
        var unchanged=before==after;
        var onlyDisable=before!=null && !after.IsEnabled && before with {IsEnabled=false}==after;
        Require(status!="ARCHIVED" || unchanged || onlyDisable,409,"archived_item");
        Require(companyEnabled || unchanged || onlyDisable,409,"company_disabled");
    }
    public static (bool CanSell,bool CanPurchase,bool CanTrackStock) Effective(Values values,string status,string kind,bool companyEnabled)
    {
        var enabled=status=="ACTIVE" && companyEnabled && values.IsEnabled;
        return (enabled && values.IsSellable,enabled && values.IsPurchasable,enabled && values.TrackStock && CatalogItemKind.SupportsStock(kind));
    }
}
