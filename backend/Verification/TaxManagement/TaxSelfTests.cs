using Enginia360.Modules.TaxManagement;
using Enginia360.Shared.Validation;
using System.Text.Json;

namespace Enginia360.Verification.TaxManagement;

public static class TaxSelfTests
{
    public static void Run()
    {
        var count=0;
        void Assert(bool condition) { if(!condition) throw new Exception("Tax domain assertion failed"); count++; }
        void Reject(Action action,string code) { try { action(); } catch(ApiException e) when(e.Code==code) {count++;return;} throw new Exception("Expected "+code); }
        var from=new DateOnly(2026,1,1);
        var country=Guid.NewGuid();
        TaxFiscalVersion V(string rate="22",string treatment="TAXABLE",Guid? nature=null,DateOnly? start=null,DateOnly? end=null)
            =>new(Guid.NewGuid(),TaxRules.ParseRate(rate),treatment,nature,null,start??from,end);
        Assert(TaxRules.ParseRate("999.999999")==999.999999m);
        Assert(TaxRules.ParseRate("0.000001")==0.000001m);
        foreach(var bad in new[]{"-1","1e2","1,5","1.0000000","1000","NaN"," 22","+22",".5","22."}) Reject(()=>TaxRules.ParseRate(bad),"tax_invalid_rate");
        Assert(TaxRules.ParseDate("2024-02-29")==new DateOnly(2024,2,29));
        foreach(var bad in new[]{"2025-02-29","2026-1-01","2026-01-01T00:00:00Z"}) Reject(()=>TaxRules.ParseDate(bad),"tax_invalid_date");
        TaxRules.Validate(V(),"IT",country,null);
        Reject(()=>TaxRules.Validate(V("0"),"IT",country,null),"tax_invalid_treatment_rate");
        Reject(()=>TaxRules.Validate(V("0","ZERO_RATED"),"IT",country,null),"tax_zero_rated_not_applicable");
        TaxRules.Validate(V("0","ZERO_RATED"),"US",country,null);
        var mappings=new[]{("EXCLUDED","N1"),("OUT_OF_SCOPE","N2.1"),("OUT_OF_SCOPE","N2.2"),("NON_TAXABLE","N3.1"),("EXEMPT","N4"),("MARGIN","N5"),("REVERSE_CHARGE","N6.3"),("OTHER_EU","N7")};
        foreach(var (treatment,code) in mappings) {
            var nature=new TaxNature(Guid.NewGuid(),country,"FATTURAPA",code,new DateOnly(2021,1,1),null);
            TaxRules.Validate(V("0",treatment,nature.Id),"IT",country,nature);count++;
            Reject(()=>TaxRules.Validate(V("1",treatment,nature.Id),"IT",country,nature),"tax_invalid_treatment_rate");
            Reject(()=>TaxRules.Validate(V("0","EXEMPT",nature.Id),"IT",Guid.NewGuid(),nature),"tax_nature_country_mismatch");
        }
        var finite=new TaxNature(Guid.NewGuid(),country,"FATTURAPA","N4",from,from.AddDays(30));
        Reject(()=>TaxRules.Validate(V("0","EXEMPT",finite.Id),"IT",country,finite),"tax_nature_validity_mismatch");
        TaxRules.Validate(V("0","EXEMPT",finite.Id,end:finite.ValidTo),"IT",country,finite);
        Reject(()=>TaxRules.Validate(V("0","EXEMPT",finite.Id,start:from.AddDays(-1),end:from),"IT",country,finite),"tax_nature_validity_mismatch");
        Reject(()=>TaxRules.Validate(V(end:from.AddDays(-1)),"IT",country,null),"tax_invalid_interval");
        var current=V();var successor=V(start:from.AddMonths(1));
        var plan=TaxRules.Schedule([current],successor);
        Assert(plan.PredecessorId==current.Id && plan.PredecessorValidTo==from.AddMonths(1).AddDays(-1));
        Reject(()=>TaxRules.Schedule([current],V()),"tax_version_overlap");
        Reject(()=>TaxRules.Schedule([current,successor],V(start:from.AddDays(1))),"tax_version_overlap");
        Assert(TaxRules.Overlaps(from,from,from,null));
        Assert(!TaxRules.Overlaps(from,from,from.AddDays(1),null));
        Assert(TaxRules.Resolve([current],from)?.Id==current.Id);
        Assert(TaxRules.Resolve([V(end:from)],from.AddDays(1))==null);
        Reject(()=>TaxRules.CheckRevision(1,2),"tax_stale_version");
        Reject(()=>TaxRules.CheckRevision(TaxRules.MaxRevision,TaxRules.MaxRevision),"tax_version_exhausted");
        using var invalid=JsonDocument.Parse("{\"values\":{},\"unexpected\":true}");
        Reject(()=>TaxInput.Object(invalid.RootElement,"values"),"tax_invalid_payload");
        using var duplicate=JsonDocument.Parse("{\"name\":\"a\",\"name\":\"b\"}");
        Reject(()=>TaxInput.Object(duplicate.RootElement,"name"),"tax_invalid_payload");
        using var numeric=JsonDocument.Parse("{\"rate\":22,\"treatment\":\"TAXABLE\",\"valid_from\":\"2026-01-01\"}");
        Reject(()=>TaxInput.Fiscal(numeric.RootElement),"tax_invalid_rate");
        using var whitespaceDate=JsonDocument.Parse("{\"validFrom\":\" 2026-01-01\"}");
        Reject(()=>TaxInput.Date(TaxInput.Object(whitespaceDate.RootElement,"validFrom"),"validFrom"),"tax_invalid_date");
        foreach(var code in new[]{" VAT_A","VAT_A ","\tVAT_A"}) {
            var values=TaxInput.Object(JsonSerializer.SerializeToElement(new {code}),"code");
            Reject(()=>TaxInput.Code(values),"tax_invalid_code");
        }
        foreach(var value in new[]{"a\u0000b","a\nb"}) {
            var values=TaxInput.Object(JsonSerializer.SerializeToElement(new {name=value}),"name");
            Reject(()=>TaxInput.Text(values,"name",150,true),"tax_invalid_field");
        }
        var wrongScheme=new TaxNature(Guid.NewGuid(),country,"OTHER","N4",from,null);
        Reject(()=>TaxRules.Validate(V("0","EXEMPT",wrongScheme.Id),"IT",country,wrongScheme),"tax_nature_treatment_mismatch");
        var future=V(start:from.AddMonths(2));
        var gap=V(start:from.AddMonths(1),end:from.AddMonths(2).AddDays(-1));
        Assert(TaxRules.Schedule([V(end:from),future],gap).PredecessorId==null);
        Assert(TaxRules.Resolve([V(end:from)],from)?.ValidTo==from);
        Assert(TaxRules.RateText(22m)=="22.000000");
        foreach(var number in Enumerable.Range(1,6)) {
            var nature=new TaxNature(Guid.NewGuid(),country,"FATTURAPA","N3."+number,from,null);
            TaxRules.Validate(V("0","NON_TAXABLE",nature.Id),"IT",country,nature);count++;
        }
        foreach(var number in Enumerable.Range(1,9)) {
            var nature=new TaxNature(Guid.NewGuid(),country,"FATTURAPA","N6."+number,from,null);
            TaxRules.Validate(V("0","REVERSE_CHARGE",nature.Id),"IT",country,nature);count++;
        }
        Assert(TaxTemplates.Italian.Any(t=>t.Code=="VAT_STANDARD" && t.Name=="IVA ordinaria"));
        Assert(!TaxTemplates.Italian.Any(t=>t.Code=="VAT_STANDARD22"));
        Assert(TaxTemplates.Italian.Length==14 && TaxTemplates.Italian.Select(t=>t.Code).Distinct().Count()==14);
        var aggregate=new TaxCode(Guid.NewGuid(),country,1,true,true,[current]);
        Assert(aggregate.ResolveVersionAt(from).Id==current.Id);
        Assert(aggregate.PlanVersion(successor,1).PredecessorId==current.Id);
        Reject(()=>aggregate.PlanVersion(successor,2),"tax_stale_version");
        var inactiveAggregate=new TaxCode(Guid.NewGuid(),country,1,false,true,[current]);
        Assert(inactiveAggregate.ResolveVersionAt(from).Id==current.Id);
        Reject(()=>inactiveAggregate.ResolveVersionAt(from,true),"tax_inactive");
        Reject(()=>inactiveAggregate.PlanVersion(successor,1),"tax_inactive");
        Reject(()=>new TaxCode(Guid.NewGuid(),country,1,true,true,[current,successor]),"tax_version_overlap");
        Console.WriteLine($"Tax domain self-tests passed ({count} assertions).");
    }
}
