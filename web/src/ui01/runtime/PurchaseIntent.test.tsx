import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import PurchaseIntent from './PurchaseIntent';
const supplier = '22222222-2222-4222-8222-222222222222', line = '11111111-1111-4111-8111-111111111111';
const response = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status });
const state = (remaining: string, intents: unknown[] = []) => ({ state: 'ready', source: { revision: 3, quantity: '3', description: 'Pastiglie' }, pending: String(3 - Number(remaining)), remaining,
  suppliers: [{ id: supplier, name: 'Fornitore sintetico', revision: 4, mappingRevision: 2 }], intents });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const mount = () => render(<PurchaseIntent url='/api/v1/inventory/orders/x/lines/y' warehouseId={line} closed={false} blocked={false} onBlocked={() => undefined} onError={() => undefined} />);
test('lost accepted purchase response is retried byte-identically, then authoritative reread shows Held without vendor identifiers', async () => {
  const posts: { body: string; path: string }[] = []; let reads = 0;
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    if (path === '/auth/csrf') return response({ requestToken: 'unit-only' });
    if (path.includes('/quote?')) return response({ state: 'ready', quote: { revision: 1, catalogVersion: 8, authorityVersion: 1, sourcePresent: true, unitPurchasePrice: '12.345678' } });
    if (options?.method === 'POST') { posts.push({ body: String(options.body), path }); if (posts.length === 1) throw new TypeError('lost'); return response({ state: 'replayed', id: 'x', status: 'Held' }, 200); }
    reads++; return response(reads === 1 ? state('3') : state('1', [{ id: '33333333-3333-4333-8333-333333333333', quantity: '2.000000', supplierId: supplier, supplierName: 'Fornitore sintetico', status: 'Held' }]));
  }));
  mount();
  await screen.findByText('Residuo richiedibile: 3');
  fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } });
  await screen.findByText('Costo unitario acquisto: 12.345678 · listino presente (revisione 1)');
  fireEvent.change(screen.getByLabelText('Quantità da richiedere'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: "Crea richiesta d'acquisto" }));
  await screen.findByText("Esito richiesta d'acquisto incerto: riprova solo il comando identico.");
  expect((screen.getByLabelText('Quantità da richiedere') as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Riprova richiesta identica' }));
  await screen.findByText('Residuo richiedibile: 1');
  expect(posts.length).toBe(2); expect(posts[1]).toEqual(posts[0]);
  expect(JSON.parse(posts[0].body)).toMatchObject({ warehouseId: line, supplierId: supplier, sourceRevision: 3, supplierRevision: 4, mappingRevision: 2, quantity: '2' });
  expect(screen.getByText(/In attesa — connettore d'acquisto non ancora attivo/)).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/vendorId|GBV|Giobby/i);
});
test('selected supplier shows only the current purchasing quote without list management', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path.includes('/quote?')
    ? response({ state: 'ready', quote: { revision: 2, catalogVersion: 8, authorityVersion: 1, sourcePresent: true, unitPurchasePrice: '12.345678' } }) : response(state('3'))));
  mount(); await screen.findByText('Residuo richiedibile: 3');
  fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } });
  await screen.findByText('Costo unitario acquisto: 12.345678 · listino presente (revisione 2)');
  expect(screen.queryByLabelText('Prezzo acquisto mancante')).toBeNull();
});

test('untouched missing quote zero never posts an accepted request', async () => {
  const posts: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    if (path === '/auth/csrf') return response({ requestToken: 'x' });
    if (options?.method === 'POST') { posts.push(String(options.body)); return response({ state: 'applied' }, 201); }
    if (path.includes('/quote?')) return response({ state: 'ready', quote: { revision: 0, catalogVersion: 8, authorityVersion: 1, sourcePresent: false, unitPurchasePrice: null } });
    return response(state('3'));
  }));
  mount(); await screen.findByText('Residuo richiedibile: 3');
  await act(async () => { fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } }); });
  fireEvent.change(screen.getByLabelText('Quantità da richiedere'), { target: { value: '1' } });
  fireEvent.click(screen.getByRole('button', { name: "Crea richiesta d'acquisto" }));
  await screen.findByText('Prezzo mancante: inserisci esplicitamente il costo, anche zero.');
  expect(posts).toHaveLength(0);
  expect((screen.getByLabelText('Prezzo acquisto mancante') as HTMLInputElement).value).toBe('0.000000');
});

test.each([false, true])('explicit acceptance sends frozen quote version and manual price only for absence (listed=%s)', async (listed) => {
  const posts: { path: string; body: string }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    if (path === '/auth/csrf') return response({ requestToken: 'x' });
    if (options?.method === 'POST') { posts.push({ path, body: String(options.body) }); return response({ state: 'applied' }, 201); }
    if (path.includes('/quote?')) return response({ state: 'ready', quote: { revision: listed ? 2 : 0, catalogVersion: 8, authorityVersion: 1, sourcePresent: listed, unitPurchasePrice: listed ? '12.345678' : null } });
    return response(state('3'));
  }));
  mount(); await screen.findByText('Residuo richiedibile: 3');
  await act(async () => { fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } }); });
  fireEvent.change(screen.getByLabelText('Quantità da richiedere'), { target: { value: '1' } });
  if (!listed) fireEvent.change(screen.getByLabelText('Prezzo acquisto mancante'), { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: "Crea richiesta d'acquisto" }));
  await screen.findByText('Richiesta registrata e riletta dal server.');
  expect(posts).toHaveLength(1);expect(posts[0].path).toBe('/api/v1/inventory/orders/x/lines/y/purchase-intents/accepted');
  expect(JSON.parse(posts[0].body)).toMatchObject({ quoteRevision: listed ? 2 : 0, catalogVersion: 8, authorityVersion: 1, manualUnitPurchasePrice: listed ? null : '0' });
});

test('authoritative reread displays accepted q6 cost and frozen source absence rather than a later list quote', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => response(state('2', [{ id: '33333333-3333-4333-8333-333333333333', quantity: '1.000000', supplierName: 'Fornitore sintetico', status: 'Held', acceptedPrice: { unitPurchasePrice: '0.000000', sourcePresent: false, revision: 0, method: 'manual' } }]))));
  mount(); await screen.findByText('Costo accettato: 0.000000 · listino assente alla conferma · inserimento operatore');
});

test('explicit reread recovers an initially unavailable quote before enabling a priced command', async () => {
  let quotes = 0;
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path.includes('/quote?')) { quotes++; return quotes === 1 ? response({ state: 'unavailable' }, 503) : response({ state: 'ready', quote: { revision: 1, catalogVersion: 8, authorityVersion: 1, sourcePresent: true, unitPurchasePrice: '12.345678' } }); }
    return response(state('3'));
  }));
  mount();await screen.findByText('Residuo richiedibile: 3');
  fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } });
  await screen.findByText('Quotazione acquisto non disponibile. Rileggi.');
  fireEvent.click(screen.getByRole('button', { name: 'Rileggi richieste e quotazione' }));
  await screen.findByText('Costo unitario acquisto: 12.345678 · listino presente (revisione 1)');
  expect(quotes).toBe(2);
});

test('quantity beyond remaining is refused locally without posting', async () => {
  const fetchMock = vi.fn(async (path: string) => path === '/auth/csrf' ? response({ requestToken: 'x' }) : path.includes('/quote?') ? response({ state: 'ready', quote: { revision: 1, catalogVersion: 8, authorityVersion: 1, sourcePresent: true, unitPurchasePrice: '12.345678' } }) : response(state('1')));
  vi.stubGlobal('fetch', fetchMock); mount();
  await screen.findByText('Residuo richiedibile: 1');
  fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } });
  await screen.findByText('Costo unitario acquisto: 12.345678 · listino presente (revisione 1)');
  fireEvent.change(screen.getByLabelText('Quantità da richiedere'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: "Crea richiesta d'acquisto" }));
  await screen.findByText('Quantità positiva, massimo 6 decimali e non oltre il residuo richiedibile.');
  expect(fetchMock.mock.calls.some(call => (call as unknown[])[1] && ((call as unknown[])[1] as RequestInit).method === 'POST')).toBe(false);
});
