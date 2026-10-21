import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorkshopEditor from './WorkshopEditor';
import type { EditorProps } from './contracts';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
export const props: EditorProps = {
    document: {
        id: 'document-synthetic', reference: 'SYN-001',
        customer: { id: 'customer', name: 'Cliente sintetico' },
        payer: { id: 'payer', name: 'Pagante sintetico distinto' },
        vehicle: { id: 'vehicle-a', label: 'Veicolo sintetico A', keeper: 'Intestatario sintetico A' },
        groups: [
            { id: 'group-a', title: 'Manutenzione sintetica', lines: [
                { id: 'service-a', kind: 'Service', catalogId: 'svc', description: 'Controllo sintetico', quantity: '1.123456', unitPrice: '45.654321' },
                { id: 'part-a', kind: 'Part', catalogId: 'part', description: 'Filtro sintetico', quantity: '2.000000', unitPrice: '12.123456' },
            ] },
            { id: 'group-b', title: 'Verifica sintetica', lines: [{ id: 'note-b', kind: 'Note', description: 'Nota sintetica' }] },
        ],
        summary: { revision: 'projection-1', net: '75.123456', tax: '16.527160', total: '91.650616' },
        operations: { reserved: '2.000000', picked: '1.000000', prepared: '0.500000', installed: '0.000000', carcass: 'Da verificare', external: 'Received' },
    },
    catalog: [{ id: 'part-filter', kind: 'Part', description: 'Filtro aria sintetico', unitPrice: '19.123456' }],
    vehicles: [{ id: 'vehicle-b', label: 'Veicolo sintetico B', keeper: 'Intestatario sintetico B' }],
    payers: [{ id: 'payer-b', name: 'Altro pagante sintetico' }],
};

test('renders supplied context, repeated groups, q6 summary and separate logistical facts without network', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<WorkshopEditor {...props} />);
    expect(screen.getByText('Prototipo — dati sintetici')).toBeTruthy();
    expect(screen.getByText('SYN-001')).toBeTruthy();
    expect(screen.getByText('Cliente sintetico')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Manutenzione sintetica' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Verifica sintetica' })).toBeTruthy();
    expect(screen.getByText('91.650616 EUR')).toBeTruthy();
    for (const name of ['Prenotato', 'Prelevato', 'In preparazione', 'Installato / consumato', 'Carcassa']) expect(screen.getByText(name)).toBeTruthy();
    expect(screen.getByText('Received · ricevuto, NON confermato')).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
});

test('explicit row editing focuses description and cancel restores row and trigger focus without emitting changes', async () => {
    const onDraftChange = vi.fn(); render(<WorkshopEditor {...props} onDraftChange={onDraftChange} />);
    expect(screen.queryByLabelText('Descrizione service-a')).toBeNull();
    const trigger = screen.getByRole('button', { name: 'Modifica service-a' });
    fireEvent.click(trigger);
    const input = screen.getByLabelText('Descrizione service-a');
    await waitFor(() => expect(document.activeElement).toBe(input));
    fireEvent.change(input, { target: { value: 'Modifica da annullare' } });
    fireEvent.click(screen.getByRole('button', { name: 'Annulla riga' }));
    expect(screen.getByText('Controllo sintetico')).toBeTruthy();
    expect(screen.queryByText('Modifica da annullare')).toBeNull();
    expect(onDraftChange).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Modifica service-a' })));
});

test('apply preserves q6 strings, stable row/group identity and immutable supplied summary while marking it stale', async () => {
    const onDraftChange = vi.fn(); render(<WorkshopEditor {...props} onDraftChange={onDraftChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Modifica part-a' }));
    fireEvent.change(screen.getByLabelText('Quantità part-a'), { target: { value: '3.123456' } });
    fireEvent.change(screen.getByLabelText('Prezzo unitario part-a'), { target: { value: '123456789012.654321' } });
    expect(screen.getByText('Riepilogo non aggiornato · modifiche locali')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Applica riga' }));
    const output = onDraftChange.mock.calls[0][0];
    expect(output.groups[0].id).toBe('group-a');
    expect(output.groups[0].lines[1]).toEqual({ ...props.document.groups[0].lines[1], quantity: '3.123456', unitPrice: '123456789012.654321' });
    expect(output.groups[1]).toBe(props.document.groups[1]);
    expect(output.summary).toBe(props.document.summary);
    expect(props.document.groups[0].lines[1]).toHaveProperty('quantity', '2.000000');
    expect(screen.getByText('Riepilogo non aggiornato · modifiche locali')).toBeTruthy();
    expect(screen.getByText('91.650616 EUR')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Modifica part-a' })));
});

test('vehicle and payer selections are independent local changes and context can collapse without losing them', () => {
    const onDraftChange = vi.fn(); render(<WorkshopEditor {...props} onDraftChange={onDraftChange} />);
    fireEvent.change(screen.getByLabelText('Seleziona veicolo sintetico'), { target: { value: 'vehicle-b' } });
    expect(screen.getByText('Intestatario: Intestatario sintetico B')).toBeTruthy();
    expect(onDraftChange.mock.calls[0][0].payer).toEqual(props.document.payer);
    fireEvent.change(screen.getByLabelText('Seleziona pagante sintetico'), { target: { value: 'payer-b' } });
    expect(onDraftChange.mock.calls[1][0].vehicle.id).toBe('vehicle-b');
    expect(onDraftChange.mock.calls[1][0].payer.id).toBe('payer-b');
    fireEvent.click(screen.getByRole('button', { name: 'Comprimi contesto' }));
    expect(screen.queryByRole('complementary', { name: 'Contesto documento' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Espandi contesto' }));
    expect(screen.getByLabelText('Seleziona pagante sintetico')).toHaveProperty('value', 'payer-b');
    expect(screen.getByLabelText('Seleziona veicolo sintetico')).toHaveProperty('value', 'vehicle-b');
});

test('loading and error are UI states that never invent document content or backend workflow policy', () => {
    render(<WorkshopEditor {...props} state="loading" />);
    expect(screen.getByRole('status').textContent).toContain('Caricamento del documento sintetico');
    expect(screen.queryByRole('button', { name: 'Modifica service-a' })).toBeNull();
    cleanup();
    render(<WorkshopEditor {...props} state="error" />);
    expect(screen.getByRole('alert').textContent).toContain('Documento non disponibile');
    expect(screen.queryByRole('button', { name: 'Modifica service-a' })).toBeNull();
    expect(screen.queryByText('91.650616 EUR')).toBeNull();
});

test('an empty document shows an explicit empty state instead of fabricated rows or totals', () => {
    const empty = { ...props.document, groups: [], summary: { revision: 'projection-empty', net: '0.000000', tax: '0.000000', total: '0.000000' } };
    render(<WorkshopEditor {...props} document={empty} />);
    expect(screen.getByText('Nessuna lavorazione fornita')).toBeTruthy();
    expect(screen.getAllByText('0.000000 EUR')).toHaveLength(3);
    expect(screen.queryByRole('button', { name: /Modifica/ })).toBeNull();
});

test('local catalog search filters by kind and text and selects into current row without changing identity', () => {
    const onDraftChange = vi.fn(); render(<WorkshopEditor {...props} onDraftChange={onDraftChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Modifica part-a' }));
    const search = screen.getByLabelText('Cerca nel catalogo sintetico');
    fireEvent.change(search, { target: { value: 'inesistente' } });
    expect(screen.getByText('Nessun risultato locale')).toBeTruthy();
    fireEvent.change(search, { target: { value: 'aria' } });
    fireEvent.click(screen.getByRole('button', { name: 'Seleziona Filtro aria sintetico' }));
    expect(screen.getByLabelText('Descrizione part-a')).toHaveProperty('value', 'Filtro aria sintetico');
    expect(screen.getByLabelText('Prezzo unitario part-a')).toHaveProperty('value', '19.123456');
    fireEvent.click(screen.getByRole('button', { name: 'Applica riga' }));
    expect(onDraftChange.mock.calls[0][0].groups[0].lines[1]).toEqual({ ...props.document.groups[0].lines[1], catalogId: 'part-filter', description: 'Filtro aria sintetico', unitPrice: '19.123456' });
});

test('Escape cancels transient input, restores summary freshness and focus, and never switches active rows', async () => {
    render(<WorkshopEditor {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Modifica service-a' }));
    const input = screen.getByLabelText('Descrizione service-a');
    fireEvent.change(input, { target: { value: 'Temporaneo' } });
    expect(screen.getByRole('button', { name: 'Modifica part-a' })).toHaveProperty('disabled', true);
    expect(screen.getByText('Riepilogo non aggiornato · modifiche locali')).toBeTruthy();
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByLabelText('Descrizione service-a')).toBeNull();
    expect(screen.getByText('Proiezione fornita · invariata')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Modifica service-a' })));
});

test.each(['', '   ', 'x'.repeat(501)])('rejects an empty or overlong description before applying Note edits: %s', value => {
    const onDraftChange = vi.fn(); render(<WorkshopEditor {...props} onDraftChange={onDraftChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Modifica note-b' }));
    const input = screen.getByLabelText('Descrizione note-b');
    fireEvent.change(input, { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: 'Applica riga' }));
    expect(onDraftChange).not.toHaveBeenCalled();
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByRole('alert').textContent).toContain('1–500');
    expect(document.activeElement).toBe(input);
});

test.each(['1.1234567', '1,25', '1e3', '-1', '', '1234567890123', 'Infinity', ' 1.2'])('rejects invalid invariant decimal %s without rounding, emits no draft and focuses associated announced error', async value => {
    const onDraftChange = vi.fn(); render(<WorkshopEditor {...props} onDraftChange={onDraftChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Modifica part-a' }));
    const input = screen.getByLabelText('Quantità part-a');
    fireEvent.change(input, { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: 'Applica riga' }));
    expect(onDraftChange).not.toHaveBeenCalled();
    expect(input).toHaveProperty('value', value);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    const error = document.getElementById(input.getAttribute('aria-describedby')!);
    expect(error?.getAttribute('role')).toBe('alert');
    expect(error?.textContent).toContain('6 decimali');
    await waitFor(() => expect(document.activeElement).toBe(input));
});
