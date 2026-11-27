using System.Text.Json;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.TaxManagement;

public static class TaxInput
{
    public static Dictionary<string,JsonElement> Object(JsonElement body,params string[] allowed)
    {
        TaxRules.Require(body.ValueKind==JsonValueKind.Object,"tax_invalid_payload");
        var result=new Dictionary<string,JsonElement>(StringComparer.Ordinal);
        foreach(var property in body.EnumerateObject())
            TaxRules.Require(allowed.Contains(property.Name,StringComparer.Ordinal) && result.TryAdd(property.Name,property.Value),"tax_invalid_payload");
        return result;
    }
    public static JsonElement Required(Dictionary<string,JsonElement> input,string key)
    {TaxRules.Require(input.ContainsKey(key),"tax_field_required",field:key);return input[key];}
    public static string? Text(Dictionary<string,JsonElement> input,string key,int max,bool required=false)
    {
        if(!input.TryGetValue(key,out var raw) || raw.ValueKind==JsonValueKind.Null) {
            TaxRules.Require(!required,"tax_field_required",field:key);return null;
        }
        TaxRules.Require(raw.ValueKind==JsonValueKind.String,"tax_invalid_field",field:key);
        var text=raw.GetString()!.Trim();
        TaxRules.Require(text.Length<=max,"tax_field_too_long",field:key);
        TaxRules.Require(!text.Any(char.IsControl),"tax_invalid_field",field:key);
        for(var i=0;i<text.Length;i++) {
            if(char.IsHighSurrogate(text[i])) {
                TaxRules.Require(i+1<text.Length && char.IsLowSurrogate(text[i+1]),"tax_invalid_field",field:key);i++;
            } else TaxRules.Require(!char.IsLowSurrogate(text[i]),"tax_invalid_field",field:key);
        }
        TaxRules.Require(!required || text.Length>0,"tax_field_required",field:key);
        return text.Length==0?null:text;
    }
    public static string Code(Dictionary<string,JsonElement> input)
    {
        var value=Text(input,"code",50,true)!;
        TaxRules.Require(input["code"].GetString()==value,"tax_invalid_code",field:"code");
        return value;
    }
    public static Guid? Id(Dictionary<string,JsonElement> input,string key,bool required=false)
    {
        if(!input.TryGetValue(key,out var raw) || raw.ValueKind==JsonValueKind.Null) {
            TaxRules.Require(!required,"tax_field_required",field:key);return null;
        }
        TaxRules.Require(raw.ValueKind==JsonValueKind.String && Guid.TryParse(raw.GetString(),out var id) && id!=Guid.Empty,"tax_invalid_id",field:key);
        return Guid.Parse(raw.GetString()!);
    }
    public static DateOnly Date(Dictionary<string,JsonElement> input,string key)
    {
        var raw=Required(input,key);
        TaxRules.Require(raw.ValueKind==JsonValueKind.String,"tax_invalid_date",field:key);
        return TaxRules.ParseDate(raw.GetString()!);
    }
    public static long Revision(Dictionary<string,JsonElement> input)
    {
        var raw=Required(input,"expectedVersion");
        TaxRules.Require(raw.ValueKind==JsonValueKind.Number && raw.TryGetInt64(out var n) && n>=1 && n<=TaxRules.MaxRevision,"tax_invalid_expected_version");
        return raw.GetInt64();
    }
    public static bool Flag(Dictionary<string,JsonElement> input,string key,bool fallback)
    {
        if(!input.TryGetValue(key,out var raw)) return fallback;
        TaxRules.Require(raw.ValueKind is JsonValueKind.True or JsonValueKind.False,"tax_invalid_field",field:key);
        return raw.GetBoolean();
    }
    public static TaxFiscalVersion Fiscal(JsonElement raw)
    {
        var input=Object(raw,"rate","treatment","tax_nature_code_id","legal_reference","valid_from","valid_to");
        var rate=Required(input,"rate");TaxRules.Require(rate.ValueKind==JsonValueKind.String,"tax_invalid_rate",field:"rate");
        var value=TaxRules.ParseRate(rate.GetString()!);
        var treatment=Text(input,"treatment",30,true)!;
        var from=Date(input,"valid_from");DateOnly? to=null;
        if(input.TryGetValue("valid_to",out var end) && end.ValueKind!=JsonValueKind.Null) to=Date(input,"valid_to");
        TaxRules.Require(to==null || to>=from,"tax_invalid_interval");
        return new(Guid.NewGuid(),value,treatment,Id(input,"tax_nature_code_id"),Text(input,"legal_reference",255),from,to);
    }
}
