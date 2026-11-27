namespace Enginia360.Modules.TaxManagement;

public static class ClassificationTemplates
{
    // Suggerimenti descrittivi: nessuna associazione a trattamento, natura, aliquota o TaxCode.
    public static readonly (string Code,string Name)[] Items=[
        ("GENERAL_GOODS","Beni generici"),("GENERAL_SERVICES","Servizi generici"),("FOOD","Alimentari"),
        ("BOOKS","Libri"),("MEDICAL_GOODS","Beni medicali"),("DIGITAL_SERVICES","Servizi digitali"),
        ("REPAIR_SERVICES","Riparazioni"),("TRANSPORT_SERVICES","Trasporto"),
        ("INTELLECTUAL_PROPERTY","Proprieta intellettuale"),("ANCILLARY_CHARGES","Oneri accessori")];
    public static readonly (string Code,string Name)[] Partners=[
        ("TAXABLE_PERSON","Soggetto passivo"),("NON_TAXABLE_PERSON","Soggetto non passivo"),("UNKNOWN","Non determinato")];
    public static (string Code,string Name)[] For(ClassificationKind kind)=>kind==ClassificationKind.Item?Items:Partners;
}
