namespace Enginia360.Modules.TaxManagement;

public sealed record TaxTemplate(string Code,string Name,decimal Rate,string Treatment,string? Nature);
public static class TaxTemplates
{
    public static readonly TaxTemplate[] Italian=[
        new("VAT_STANDARD","IVA ordinaria",22m,"TAXABLE",null),
        new("VAT_REDUCED_10","IVA ridotta 10%",10m,"TAXABLE",null),
        new("VAT_REDUCED_5","IVA ridotta 5%",5m,"TAXABLE",null),
        new("VAT_REDUCED_4","IVA ridotta 4%",4m,"TAXABLE",null),
        new("VAT_EXCLUDED","Escluso IVA",0m,"EXCLUDED","N1"),
        new("VAT_OUT_OF_SCOPE_1","Non soggetto IVA - articolo 7",0m,"OUT_OF_SCOPE","N2.1"),
        new("VAT_OUT_OF_SCOPE_2","Non soggetto IVA - altri casi",0m,"OUT_OF_SCOPE","N2.2"),
        new("VAT_EXPORT","Non imponibile - esportazioni",0m,"NON_TAXABLE","N3.1"),
        new("VAT_EU_SUPPLY","Non imponibile - cessioni intracomunitarie",0m,"NON_TAXABLE","N3.2"),
        new("VAT_EXEMPT","Esente IVA",0m,"EXEMPT","N4"),
        new("VAT_MARGIN","Regime del margine",0m,"MARGIN","N5"),
        new("VAT_RC_SCRAP","Inversione contabile - rottami",0m,"REVERSE_CHARGE","N6.1"),
        new("VAT_RC_BUILDING","Inversione contabile - subappalto edile",0m,"REVERSE_CHARGE","N6.3"),
        new("VAT_OTHER","IVA assolta in altro Stato UE",0m,"OTHER_EU","N7")
    ];
}
