// UI01.a local prototype contract. Not a domain DTO, permission or persistence API.
export type Party = Readonly<{ id: string; name: string }>;
export type Vehicle = Readonly<{ id: string; label: string; keeper: string }>;
export type EditorLine = Readonly<{ id: string; description: string } & (
    { kind: 'Note' } | { kind: 'Service' | 'Part'; catalogId: string; quantity: string; unitPrice: string }
)>;
export type EditorWorkGroup = Readonly<{ id: string; title: string; lines: readonly EditorLine[] }>;
export type EditorSummary = Readonly<{ revision: string; net: string; tax: string; total: string }>;
export type OperationalProjection = Readonly<{
    reserved: string; picked: string; prepared: string; installed: string; carcass: string;
    external: 'Pending' | 'Received' | 'Confirmed' | 'Error';
}>;
export type EditorDocument = Readonly<{
    id: string; reference: string; customer: Party; payer: Party; vehicle: Vehicle;
    groups: readonly EditorWorkGroup[]; summary: EditorSummary; operations: OperationalProjection;
}>;
export type CatalogItem = Readonly<{ id: string; kind: 'Service' | 'Part'; description: string; unitPrice: string }>;
export type EditorProps = Readonly<{
    document: EditorDocument; catalog: readonly CatalogItem[]; vehicles: readonly Vehicle[];
    payers: readonly Party[]; state?: 'ready' | 'loading' | 'error';
    onDraftChange?: (document: EditorDocument) => void;
}>;
