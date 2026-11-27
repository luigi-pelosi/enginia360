using System.Globalization;
using System.Text.Json;
namespace Enginia360.Modules.TaxManagement;

/// <summary>Parser rigoroso condiviso: nessuna coercizione o proprietà ignorata.</summary>
public static class TaxRuleInput
{
    public static void Require(bool ok,string code,int status=400,string? field=null)=>TaxRules.Require(ok,code,status,field);
    public static Dictionary<string,JsonElement> Object(JsonElement raw,params string[] allowed)
    {
        Require(raw.ValueKind==JsonValueKind.Object,"tax_invalid_payload");
        var result=new Dictionary<string,JsonElement>(StringComparer.Ordinal);
        foreach(var p in raw.EnumerateObject()) {
            Require(allowed.Contains(p.Name,StringComparer.Ordinal),"tax_unknown_field",field:p.Name);
            Require(result.TryAdd(p.Name,p.Value),"tax_duplicate_field",field:p.Name);
        }
        return result;
    }
    public static JsonElement Required(Dictionary<string,JsonElement> o,string k)=>o.TryGetValue(k,out var v)?v:throw new Enginia360.Shared.Validation.ApiException(400,"tax_field_required",k);
    public static string? Text(Dictionary<string,JsonElement> o,string k,int max,bool required=false)
    {
        // Validare gli escape prima di GetString: System.Text.Json può rifiutare surrogate isolati.
        if(o.TryGetValue(k,out var raw) && raw.ValueKind==JsonValueKind.String) {
            var json=raw.GetRawText();
            for(var i=1;i<json.Length-1;i++) {
                if(json[i]!='\\')continue;
                if(i+1>=json.Length-1)break;
                if(json[i+1]!='u'){i++;continue;}
                var n=int.Parse(json.AsSpan(i+2,4),NumberStyles.HexNumber,CultureInfo.InvariantCulture);
                if(n is >=0xD800 and <=0xDBFF) {
                    Require(i+11<json.Length && json[i+6]=='\\' && json[i+7]=='u' && int.TryParse(json.AsSpan(i+8,4),NumberStyles.HexNumber,CultureInfo.InvariantCulture,out var low) && low is >=0xDC00 and <=0xDFFF,"tax_invalid_field",field:k);i+=11;
                } else {Require(n is <0xDC00 or >0xDFFF,"tax_invalid_field",field:k);i+=5;}
            }
        }
        return TaxInput.Text(o,k,max,required);
    }
    public static Guid? Id(Dictionary<string,JsonElement> o,string k,bool required=false)
    {
        if(!o.TryGetValue(k,out var raw)||raw.ValueKind==JsonValueKind.Null){Require(!required,"tax_field_required",field:k);return null;}
        var s=Text(o,k,36,true)!;
        Require(raw.GetString()==s && Guid.TryParseExact(s,"D",out _),"tax_invalid_id",field:k);
        var id=Guid.Parse(s);Require(id!=Guid.Empty,"tax_invalid_id",field:k);return id;
    }
    public static DateOnly Date(Dictionary<string,JsonElement> o,string k)
    {
        var s=Text(o,k,10,true);Require(o[k].GetString()==s && DateOnly.TryParseExact(s,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out _),"tax_invalid_date",field:k);return DateOnly.ParseExact(s!,"yyyy-MM-dd",CultureInfo.InvariantCulture);
    }
    public static JsonElement[] Array(JsonElement raw,string field,int max)
    {Require(raw.ValueKind==JsonValueKind.Array && raw.GetArrayLength()<=max,"tax_invalid_field",field:field);return raw.EnumerateArray().ToArray();}
    public static long Revision(Dictionary<string,JsonElement> o)
    {
        var raw=Required(o,"expectedVersion");Require(raw.ValueKind==JsonValueKind.Number && raw.TryGetInt64(out var revision) && revision>=1 && revision<=TaxRules.MaxRevision,"tax_invalid_expected_version",field:"expectedVersion");return raw.GetInt64();
    }
    public static TaxRuleVersion Version(JsonElement raw,int number=1,Guid? id=null,bool revision=false)
    {
        var o=Object(raw,revision?["values","conditions","expectedVersion"]:["values","conditions"]);
        var v=Object(Required(o,"values"),"tax_code_id","priority","operation_type","legal_reference","valid_from","valid_to");
        var priority=100;
        if(v.TryGetValue("priority",out var p)){Require(p.ValueKind==JsonValueKind.Number && p.TryGetInt32(out priority),"tax_invalid_field",field:"priority");}
        var operation=Text(v,"operation_type",8,true)!;Require(operation is "SALE" or "PURCHASE","tax_invalid_field",field:"operation_type");
        var from=Date(v,"valid_from");DateOnly? to=v.TryGetValue("valid_to",out var end)&&end.ValueKind!=JsonValueKind.Null?Date(v,"valid_to"):null;
        Require(to==null || to>=from,"tax_invalid_interval",field:"valid_to");
        var conditions=Array(Required(o,"conditions"),"conditions",100).Select(c=>{
            var x=Object(c,"field","operator","value");var value=Required(x,"value").Clone();
            // Valori testuali sottoposti agli stessi controlli Unicode dei metadati.
            foreach(var e in value.ValueKind==JsonValueKind.Array?value.EnumerateArray().ToArray():new[]{value})
                if(e.ValueKind==JsonValueKind.String)_=Text(new(){["value"]=e},"value",255,true);
            return new TaxRuleCondition(Guid.NewGuid(),Text(x,"field",80,true)!,Text(x,"operator",20,true)!,value);
        }).ToArray();
        return new(id??Guid.NewGuid(),number,Id(v,"tax_code_id",true)!.Value,priority,operation,"DRAFT",Text(v,"legal_reference",255,true)!,from,to,conditions);
    }
    public static Guid? QueryId(HttpContext ctx,string key)
    {
        if(!ctx.Request.Query.ContainsKey(key))return null;
        return Id(new(){[key]=JsonSerializer.SerializeToElement(ctx.Request.Query[key].ToString())},key,true);
    }
    public static DateOnly? QueryDate(HttpContext ctx,string key="date")=>!ctx.Request.Query.ContainsKey(key)?null:Date(new(){[key]=JsonSerializer.SerializeToElement(ctx.Request.Query[key].ToString())},key);
    public static (int Page,int Size) Paging(HttpContext ctx)
    {
        int Parse(string k,int fallback,int max){if(!ctx.Request.Query.ContainsKey(k))return fallback;Require(int.TryParse(ctx.Request.Query[k],NumberStyles.None,CultureInfo.InvariantCulture,out var n)&&n>=1&&n<=max,"tax_invalid_paging",field:k);return n;}
        return(Parse("page",1,100000),Parse("pageSize",25,100));
    }
    public static string Search(HttpContext ctx)=>Text(new(){["search"]=JsonSerializer.SerializeToElement(ctx.Request.Query["search"].ToString())},"search",200)??"";
}
