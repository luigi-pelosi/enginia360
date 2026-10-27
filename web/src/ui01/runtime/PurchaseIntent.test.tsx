import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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
    if (options?.method === 'POST') { posts.push({ body: String(options.body), path }); if (posts.length === 1) throw new TypeError('lost'); return response({ state: 'replayed', id: 'x', status: 'Held' }, 200); }
    reads++; return response(reads === 1 ? state('3') : state('1', [{ id: '33333333-3333-4333-8333-333333333333', quantity: '2.000000', supplierId: supplier, supplierName: 'Fornitore sintetico', status: 'Held' }]));
  }));
  mount();
  await screen.findByText('Residuo richiedibile: 3');
  fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } });
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
test('quantity beyond remaining is refused locally without posting', async () => {
  const fetchMock = vi.fn(async (path: string) => path === '/auth/csrf' ? response({ requestToken: 'x' }) : response(state('1')));
  vi.stubGlobal('fetch', fetchMock); mount();
  await screen.findByText('Residuo richiedibile: 1');
  fireEvent.change(screen.getByLabelText('Fornitore'), { target: { value: supplier } });
  fireEvent.change(screen.getByLabelText('Quantità da richiedere'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: "Crea richiesta d'acquisto" }));
  await screen.findByText('Quantità positiva, massimo 6 decimali e non oltre il residuo richiedibile.');
  expect(fetchMock.mock.calls.some(call => (call as unknown[])[1] && ((call as unknown[])[1] as RequestInit).method === 'POST')).toBe(false);
});
