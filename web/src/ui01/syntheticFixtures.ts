// Explicitly synthetic prototype data. No real customer, vehicle, price or stock fact.
import type { CatalogItem, EditorDocument, EditorLine, EditorWorkGroup, Party, Vehicle } from './contracts';

export const prototypeVehicles: readonly Vehicle[] = [
    { id: 'vehicle-sintetico-1', label: 'Veicolo sintetico 1 · furgone', keeper: 'Intestatario sintetico 1' },
    { id: 'vehicle-sintetico-2', label: 'Veicolo sintetico 2 · autocarro', keeper: 'Intestatario sintetico 2' },
];

export const prototypePayers: readonly Party[] = [
    { id: 'payer-sintetico-1', name: 'Pagante sintetico 1' },
    { id: 'payer-sintetico-2', name: 'Pagante sintetico 2' },
];

export const prototypeCatalog: readonly CatalogItem[] = [
    { id: 'svc-sintetico-1', kind: 'Service', description: 'Manodopera sintetica diagnosi', unitPrice: '42.500000' },
    { id: 'svc-sintetico-2', kind: 'Service', description: 'Manodopera sintetica sostituzione', unitPrice: '38.250000' },
    { id: 'part-sintetico-1', kind: 'Part', description: 'Filtro sintetico aria', unitPrice: '19.123456' },
    { id: 'part-sintetico-2', kind: 'Part', description: 'Guarnizione sintetica', unitPrice: '4.090000' },
    { id: 'part-sintetico-3', kind: 'Part', description: 'Lubrificante sintetico 5 litri', unitPrice: '31.750000' },
];

function line(index: number): EditorLine {
    const id = `line-sintetica-${String(index).padStart(3, '0')}`;
    if (index % 10 === 0) return { id, kind: 'Note', description: `Nota operativa sintetica ${index}` };
    if (index % 3 === 0) {
        const item = prototypeCatalog[1];
        return { id, kind: 'Service', catalogId: item.id, description: `${item.description} ${index}`, quantity: '1.500000', unitPrice: item.unitPrice };
    }
    const item = prototypeCatalog[2 + (index % 3)];
    return { id, kind: 'Part', catalogId: item.id, description: `${item.description} ${index}`, quantity: '2.250000', unitPrice: item.unitPrice };
}

const longGroups: readonly EditorWorkGroup[] = Array.from({ length: 10 }, (_, group) => ({
    id: `group-sintetico-${group + 1}`,
    title: `Lavorazione sintetica ripetuta ${group + 1}`,
    lines: Array.from({ length: 10 }, (_, row) => line(group * 10 + row + 1)),
}));

const context = {
    customer: { id: 'customer-sintetico-1', name: 'Cliente sintetico 1' },
    payer: prototypePayers[0],
    vehicle: prototypeVehicles[0],
    operations: {
        reserved: '12.000000', picked: '7.000000', prepared: '3.000000', installed: '2.000000',
        carcass: 'Rientro sintetico non verificato', external: 'Received',
    },
} as const;

export const longDocument: EditorDocument = {
    id: 'document-sintetico-lungo', reference: 'SINT-100', ...context, groups: longGroups,
    summary: { revision: 'projection-sintetica-lunga', net: '2481.250000', tax: '545.875000', total: '3027.125000' },
};

export const shortDocument: EditorDocument = {
    id: 'document-sintetico-breve', reference: 'SINT-003', ...context,
    groups: [longGroups[0], longGroups[1]].map(group => ({ ...group, lines: group.lines.slice(0, 3) })),
    summary: { revision: 'projection-sintetica-breve', net: '148.875000', tax: '32.752500', total: '181.627500' },
};

export const emptyDocument: EditorDocument = {
    id: 'document-sintetico-vuoto', reference: 'SINT-000', ...context, groups: [],
    summary: { revision: 'projection-sintetica-vuota', net: '0.000000', tax: '0.000000', total: '0.000000' },
};
