import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import OrderWorkspace from './OrderWorkspace';
import { parseEditor, type Editor } from './editorContracts';
import { capabilities, editorView, id, order, policy, summary } from './editorFixtures';
const g1 = '33333333-3333-4333-8333-333333333333', s1 = '44444444-4444-4444-8444-444444444444', p1 = '55555555-5555-4555-8555-555555555555', n1 = '66666666-6666-4666-8666-666666666666';
const line = (rid: string, kind: string) => ({ id: rid, orderId: id, catalogItemId: id, catalogVersion: 8, catalogLabel: 'Voce ' + kind, kind, quantity: '2', unitPrice: '10', discountPercent: '0', netAmount: '20.000000', taxRate: '22', payerId: id, workingGroupId: g1, configurationVersion: 9 });
const view = (extra: Record<string, unknown> = {}) => parseEditor({ ...editorView, revision: 5, groups: [{ id: g1, title: 'Cambio olio', version: 1, sequence: 1 }],
  rows: [{ id: s1, kind: 'Service', workingGroupId: g1, sequence: 2, version: 1, description: null, line: line(s1, 'Service') }, { id: p1, kind: 'Part', workingGroupId: g1, sequence: 3, version: 1, description: 'Filtro', line: line(p1, 'Part') },
    { id: n1, kind: 'Note', workingGroupId: g1, sequence: 4, version: 1, description: 'Cliente presente', line: null }],
  summary: { ...summary, revision: 5, lines: [line(s1, 'Service'), line(p1, 'Part')], netAmount: '40.000000', taxAmount: '8.800000', total: '48.800000' }, ...extra }, id);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function api(handler: (body: Record<string, unknown>) => Response | Promise<Response>) {
  const fetch = vi.fn(async (path: string, options?: RequestInit) => path === '/auth/csrf' ? new Response('{"requestToken":"test-only"}') : options?.method === 'POST' ? handler(JSON.parse(options.body as string)) : new Response('[]'));
  vi.stubGlobal('fetch', fetch); return fetch;
}
const posts = (fetch: ReturnType<typeof api>) => fetch.mock.calls.filter(([, o]) => (o as RequestInit | undefined)?.method === 'POST').map(([, o]) => JSON.parse((o as RequestInit).body as string));
test('authoritative reread revision change discards an old edit instead of rebasing it silently', () => {
  api(receipt);
  const original = view();
  const { rerender } = render(<OrderWorkspace editor={original} onApplied={async () => undefined} onError={() => undefined} />);
  fireEvent.click(document.getElementById('row-' + s1)!);
  fireEvent.change(screen.getByLabelText('Quantità riga'), { target: { value: '3' } });
  const fresh = { ...original, revision: 6, summary: { ...original.summary, revision: 6 } };
  rerender(<OrderWorkspace editor={fresh} onApplied={async () => undefined} onError={() => undefined} />);
  expect(screen.queryByLabelText('Quantità riga')).toBeNull();
});

const receipt = (b: Record<string, unknown>) => new Response(JSON.stringify({ commandId: b.commandId, orderId: id, appliedRevision: 6, resultKind: 'Updated', targetId: id }));

test('server policy and revision drive every command; no manual setup number; server capability false keeps Part structural controls unavailable', async () => {
  const fetch = api(receipt); const applied = vi.fn().mockResolvedValue(undefined);
  render(<OrderWorkspace editor={view()} onApplied={applied} onError={() => undefined} />);
  expect(screen.getByText(/Documento v7 · Policy righe v9 · Struttura v1 · Revisione 5/)).toBeTruthy();
  expect(screen.queryByLabelText(/setup/i)).toBeNull();
  const remove = screen.getAllByRole('button', { name: 'Rimuovi' });
  expect(remove.map(b => (b as HTMLButtonElement).disabled)).toEqual([false, true, false]);
  expect(remove[1].getAttribute('title')).toBe(capabilities.materialStructureEditReason);
  for (const name of ['Cambia testata', 'Cambia pagante', 'Cambia veicolo']) expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getAllByRole('button', { name: 'Modifica' })[1]);
  expect(screen.queryByLabelText('Quantità riga')).toBeNull();
  fireEvent.change(screen.getByLabelText('Prezzo riga'), { target: { value: '12.5' } });
  fireEvent.keyDown(screen.getByLabelText('Prezzo riga'), { key: 'Enter' });
  await waitFor(() => expect(applied).toHaveBeenCalledOnce());
  expect(posts(fetch)[0]).toMatchObject({ type: 'EditCommercialLine', expectedRevision: 5, expectedLinePolicyVersion: 9, expectedStructurePolicyVersion: 1, lineId: p1, unitPrice: '12.5', quantity: null });
});

test('uncertain transport freezes the command and replays byte-identical; definitive 409 shows Italian reason and unfreezes', async () => {
  let attempts = 0;
  const fetch = api(b => { attempts++; if (attempts === 1) throw new TypeError('lost'); return receipt(b); });
  render(<OrderWorkspace editor={view()} onApplied={async () => undefined} onError={() => undefined} />);
  fireEvent.change(screen.getByLabelText('Nuova lavorazione'), { target: { value: 'Freni' } });
  fireEvent.click(screen.getByRole('button', { name: 'Aggiungi lavorazione' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Riprova comando identico' }));
  await waitFor(() => expect(posts(fetch)).toHaveLength(2));
  expect(JSON.stringify(posts(fetch)[0])).toBe(JSON.stringify(posts(fetch)[1]));
  cleanup();
  api(() => new Response(JSON.stringify({ code: 'revision_changed' }), { status: 409 }));
  render(<OrderWorkspace editor={view()} onApplied={async () => undefined} onError={() => undefined} />);
  fireEvent.change(screen.getByLabelText('Nuova lavorazione'), { target: { value: 'Altro' } });
  fireEvent.click(screen.getByRole('button', { name: 'Aggiungi lavorazione' }));
  expect(await screen.findByText(/La commessa è cambiata da un altro comando/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Riprova comando identico' })).toBeNull();
});

test('invalid first field receives focus and nothing is sent; Escape cancels an edit', async () => {
  const fetch = api(receipt);
  render(<OrderWorkspace editor={view()} onApplied={async () => undefined} onError={() => undefined} />);
  fireEvent.click(screen.getByRole('button', { name: 'Aggiungi riga' }));
  expect(await screen.findByText('Seleziona articolo o prestazione.')).toBeTruthy();
  fireEvent.click(screen.getAllByRole('button', { name: 'Modifica' })[0]);
  fireEvent.keyDown(screen.getByLabelText('Descrizione riga'), { key: 'Escape' });
  expect(screen.queryByLabelText('Descrizione riga')).toBeNull();
  expect(posts(fetch)).toHaveLength(0);
});

test('closed order and missing policy are read-only with the reason', () => {
  render(<OrderWorkspace editor={view({ capabilities: { ...capabilities, closed: true } })} onApplied={async () => undefined} onError={() => undefined} />);
  expect(screen.getByText(/Commessa chiusa tecnicamente/, { selector: '[role=alert]' })).toBeTruthy();
  for (const name of ['Aggiungi lavorazione', 'Aggiungi riga', 'Aggiungi nota']) expect(screen.getByRole('button', { name }).matches(':disabled')).toBe(true);
  expect(screen.getAllByRole('button', { name: 'Modifica' }).every(b => b.matches(':disabled'))).toBe(true);
});

test('editor parser rejects an unknown group, a mismatched revision and summary rows that differ from the editor rows', () => {
  const good = JSON.parse(JSON.stringify(view())) as Editor;
  expect(() => parseEditor({ ...good, summary: { ...good.summary, revision: 4 } }, id)).toThrow();
  expect(() => parseEditor({ ...good, rows: good.rows.map(r => ({ ...r, workingGroupId: '99999999-9999-4999-8999-999999999999' })) }, id)).toThrow();
  expect(() => parseEditor({ ...good, summary: { ...good.summary, lines: [] } }, id)).toThrow();
  expect(() => parseEditor({ ...good, linePolicy: { ...policy, state: 'ready', currentLinePolicyVersion: null } }, id)).toThrow();
  expect(parseEditor({ ...good, linePolicy: { ...policy, state: 'line_policy_missing', currentLinePolicyVersion: null } }, id).linePolicy.currentLinePolicyVersion).toBeNull();
  expect(order.id).toBe(id);
});

test('after Apply and after Cancel the focus returns to the stable row action', async () => {
  api(receipt);
  render(<OrderWorkspace editor={view()} onApplied={async () => undefined} onError={() => undefined} />);
  fireEvent.click(document.getElementById('row-' + s1)!);
  fireEvent.keyDown(screen.getByLabelText('Descrizione riga'), { key: 'Escape' });
  await waitFor(() => expect(document.activeElement?.id).toBe('row-' + s1));
  fireEvent.click(document.getElementById('row-' + p1)!);
  fireEvent.change(screen.getByLabelText('Prezzo riga'), { target: { value: '11' } });
  fireEvent.keyDown(screen.getByLabelText('Prezzo riga'), { key: 'Enter' });
  await waitFor(() => expect(document.activeElement?.id).toBe('row-' + p1));
});
