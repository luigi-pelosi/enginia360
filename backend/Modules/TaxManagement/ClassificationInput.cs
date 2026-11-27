using System.Globalization;
using System.Text.Json;
using Enginia360.Shared.Validation;
namespace Enginia360.Modules.TaxManagement;

public static class ClassificationInput
{
    private static T Read<T>(Func<T> read,string prefix,string field="values")
    {
        try{return read();}
        catch(ApiException e) {throw new ApiException(e.Status,e.Code.StartsWith(prefix+"_",StringComparison.Ordinal)?e.Code:prefix+e.Code[3..],e.Field??field);}
        catch(InvalidOperationException) {throw new ApiException(400,prefix+"_invalid_field",field);}
        catch(ArgumentException) {throw new ApiException(400,prefix+"_invalid_field",field);}
    }
    public static Dictionary<string,JsonElement> Object(JsonElement raw,string prefix,params string[] fields)=>Read(()=>TaxInput.Object(raw,fields),prefix);
    public static JsonElement Required(Dictionary<string,JsonElement> input,string key,string prefix)=>Read(()=>TaxInput.Required(input,key),prefix,key);
    public static Guid Id(Dictionary<string,JsonElement> input,string key,string prefix)=>Read(()=>TaxInput.Id(input,key,true)!.Value,prefix,key);
    public static string? Text(Dictionary<string,JsonElement> input,string key,int max,bool required=false)=>Read(()=>TaxInput.Text(input,key,max,required),"tax_classification",key);
    public static string Code(Dictionary<string,JsonElement> input)=>Read(()=>TaxInput.Code(input),"tax_classification","code");
    public static DateOnly Date(string text,string field)
    {
        ClassificationTimeline.Require(DateOnly.TryParseExact(text,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out _),"tax_profile_invalid_date",field:field);
        return DateOnly.ParseExact(text,"yyyy-MM-dd",CultureInfo.InvariantCulture);
    }
    public static long Revision(Dictionary<string,JsonElement> input,string prefix)
    {
        var raw=Required(input,"expectedVersion",prefix);
        ClassificationTimeline.Require(raw.ValueKind==JsonValueKind.Number && raw.TryGetInt64(out var n) && n>=(prefix=="tax_profile"?0:1) && n<=ClassificationTimeline.MaxRevision,prefix+"_invalid_expected_version",field:"expectedVersion");
        return raw.GetInt64();
    }
    public static ClassificationProfile Profile(JsonElement raw,ClassificationKind kind)
    {
        const string prefix="tax_profile";
        var input=Object(raw,prefix,"country_id","tax_type_id",kind.ClassificationColumn,"valid_from","valid_to");
        DateOnly ReadDate(string field) {
            var value=Required(input,field,prefix);
            ClassificationTimeline.Require(value.ValueKind==JsonValueKind.String,"tax_profile_invalid_date",field:field);
            return Read(()=>Date(value.GetString()!,field),prefix,field);
        }
        var profile=new ClassificationProfile(Guid.NewGuid(),Id(input,"country_id",prefix),Id(input,"tax_type_id",prefix),Id(input,kind.ClassificationColumn,prefix),ReadDate("valid_from"),input.TryGetValue("valid_to",out var end) && end.ValueKind!=JsonValueKind.Null?ReadDate("valid_to"):null,0);
        ClassificationTimeline.Validate(profile);return profile;
    }
}

/// <summary>Solo questi valori fissi possono comporre identificatori SQL o risorse dei permessi.</summary>
public sealed class ClassificationKind
{
    private ClassificationKind(string name,string subjects,string subjectTable,string subjectColumn,string classificationColumn)
    {Name=name;Subjects=subjects;SubjectTable=subjectTable;SubjectColumn=subjectColumn;ClassificationColumn=classificationColumn;}
    public static readonly ClassificationKind Item=new("item","items","catalog_item","item_id","item_tax_classification_id");
    public static readonly ClassificationKind Partner=new("partner","partners","business_partner","business_partner_id","partner_tax_classification_id");
    public string Name {get;}
    public string Subjects {get;}
    public string SubjectTable {get;}
    public string SubjectColumn {get;}
    public string ClassificationColumn {get;}
    public string ClassificationTable => Name+"_tax_classifications";
    public string ProfileTable => Name+"_tax_profiles";
    public string ClassificationResource => "tax-"+Name+"-classifications";
    public string ProfileResource => "tax-"+Name+"-profiles";
    public string BaseRead => Name=="item"?"catalog-items.read":"business-partners.read";
    public static ClassificationKind Parse(string text)=>text switch {"item"=>Item,"partner"=>Partner,_=>throw new ApiException(400,"tax_classification_invalid_kind","kind")};
}
