namespace Enginia360.Modules.TaxManagement;

public static class TaxAuditChanges
{
    public static object Metadata(IReadOnlyDictionary<string,object?> before,IReadOnlyDictionary<string,object?> after)
    {
        var previous=new Dictionary<string,object?> { ["version"]=before["version"] };
        var current=new Dictionary<string,object?> { ["version"]=after["version"] };
        foreach(var key in new[]{"name","description"}) {
            if(Equals(before[key],after[key])) continue;
            previous[key]=before[key];current[key]=after[key];
        }
        return new {before=previous,after=current};
    }

    public static object Fiscal(TaxFiscalVersion version)=>new {
        id=version.Id,rate=TaxRules.RateText(version.Rate),treatment=version.Treatment,
        tax_nature_code_id=version.TaxNatureCodeId,legal_reference=version.LegalReference,
        valid_from=version.ValidFrom,valid_to=version.ValidTo
    };
}
