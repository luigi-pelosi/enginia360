using Enginia360.Api.Resources;
using Enginia360.Modules.Geography;
using Enginia360.Shared.Validation;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Enginia360.Modules.BusinessPartners;

// Parser esplicito: proprietà ignote/duplicate e testi non rappresentabili in PostgreSQL rifiutati.
public static class PartnerInput
{
    // Il contesto è facoltativo: i consumatori preesistenti conservano il contratto generico.
    public static void Require(bool valid,string code,string? field,int status=400)
    {
        if(!valid) throw new ApiException(status,field==null ? "validation_error" : code,field);
    }
    public static Dictionary<string,JsonElement> Object(JsonElement body,params string[] allowed)
    {
        Check.Require(body.ValueKind==JsonValueKind.Object);
        var result=new Dictionary<string,JsonElement>(StringComparer.Ordinal);
        foreach(var p in body.EnumerateObject()) Check.Require(allowed.Contains(Resources.ReadName(p),StringComparer.Ordinal) && result.TryAdd(p.Name,p.Value));
        return result;
    }
    public static string? Text(Dictionary<string,JsonElement> obj,string key,int max=500,bool required=false,string? field=null,
        string requiredCode="field_required",string invalidCode="invalid_field_value",string lengthCode="field_too_long")
    {
        if(!obj.TryGetValue(key,out var value) || value.ValueKind==JsonValueKind.Null) {Require(!required,requiredCode,field);return null;}
        string text;
        try {text=Resources.ReadString(value).Trim();}
        catch(ApiException) {throw new ApiException(400,field==null ? "validation_error" : invalidCode,field);}
        Require(text.Length<=max,lengthCode,field);
        Require(!text.Any(char.IsControl),invalidCode,field);
        for(var i=0;i<text.Length;i++) {
            if(char.IsHighSurrogate(text[i])) {Require(i+1<text.Length && char.IsLowSurrogate(text[i+1]),invalidCode,field);i++;}
            else Require(!char.IsLowSurrogate(text[i]),invalidCode,field);
        }
        Require(!required || text.Length>0,requiredCode,field); return text.Length==0 ? null : text;
    }
    public static string Choice(Dictionary<string,JsonElement> obj,string key,params string[] options)=>ChoiceAt(obj,key,null,options);
    public static string ChoiceAt(Dictionary<string,JsonElement> obj,string key,string? field,string[] options,string code="invalid_choice",string requiredCode="field_required")
    {
        var text=Text(obj,key,50,true,field,requiredCode,code,code)!; Require(options.Contains(text,StringComparer.Ordinal),code,field);return text;
    }
    public static string Country(Dictionary<string,JsonElement> obj,string? field=null,string requiredCode="field_required")
    {
        var country=Text(obj,"country_code",2,true,field,requiredCode,"invalid_country_code","invalid_country_code")!;
        Require(CountryCodes.All.Contains(country,StringComparer.Ordinal),"invalid_country_code",field);return country;
    }
    public static bool Flag(Dictionary<string,JsonElement> obj,string key,string? field=null)
    {
        if(!obj.TryGetValue(key,out var value)) return false;
        Require(value.ValueKind is JsonValueKind.True or JsonValueKind.False,"invalid_field_value",field);return value.GetBoolean();
    }
    public static long Integer(Dictionary<string,JsonElement> obj,string key,long min,long max)
    {
        Check.Require(obj.TryGetValue(key,out var value) && value.ValueKind==JsonValueKind.Number && value.TryGetInt64(out var number) && number>=min && number<=max);
        return value.GetInt64();
    }
    public static JsonElement[] Array(JsonElement value,int max=100)
    {
        Check.Require(value.ValueKind==JsonValueKind.Array && value.GetArrayLength()<=max);return value.EnumerateArray().ToArray();
    }
    public static string NormalizeTax(string value)=>Regex.Replace(value.ToUpperInvariant(),@"[\s.\-]","");
}
