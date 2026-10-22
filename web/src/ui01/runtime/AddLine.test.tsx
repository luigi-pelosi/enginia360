import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AddLine from './AddLine';
const id = '11111111-1111-4111-8111-111111111111';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test('explicit line policy version, q6 payload, current revision and exact uncertain replay; no client totals', async () => {
  let attempts = 0;
  const fetch = vi.fn(async (path: string, options?: RequestInit) => {
    if (path === '/auth/csrf') return new Response('{"requestToken":"test-only"}');
    if (options?.method === 'POST') { attempts++; if (attempts === 1) throw new TypeError('connection lost'); return new Response(JSON.stringify({ id: JSON.parse(options.body as string).id })); }
    return new Response(JSON.stringify([{ id, kind: 'Service', label: 'Servizio server', version: 8 }]));
  }); vi.stubGlobal('fetch', fetch);
  const saved = vi.fn().mockResolvedValue(undefined);
  render(<AddLine order={{ id, legalEntityId: id, siteId: id, documentTypeId: id, configurationVersion: 7, payerId: id, vehicleId: id, vehicleHolderId: id, isCustomerOrder: true }} summary={{ orderId: id, payerId: id, revision: 0, lines: [], netAmount: '0.000000', taxAmount: '0.000000', total: '0.000000', currency: 'EUR', policy: 'Case001' }} onSaved={saved} onError={() => {}} />);
  await screen.findByRole('option', { name: 'Service · Servizio server' });
  fireEvent.change(screen.getByLabelText('Articolo / prestazione'), { target: { value: id } });
  expect((screen.getByRole('button', { name: 'Aggiungi riga' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Versione configurazione righe (setup)'), { target: { value: '9' } });
  fireEvent.change(screen.getByLabelText('Quantità'), { target: { value: '1.123456' } });
  fireEvent.change(screen.getByLabelText('Prezzo unitario'), { target: { value: '45.654321' } });
  fireEvent.change(screen.getByLabelText('Sconto %'), { target: { value: '12.34' } });
  fireEvent.click(screen.getByRole('button', { name: 'Aggiungi riga' }));
  await screen.findByRole('button', { name: 'Riprova comando identico' });
  fireEvent.click(screen.getByRole('button', { name: 'Riprova comando identico' }));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  const posts = fetch.mock.calls.filter(([,o]) => o?.method === 'POST');
  expect(posts[0][1]?.body).toBe(posts[1][1]?.body);
  expect(JSON.parse(posts[0][1]?.body as string)).toEqual({ id: expect.any(String), catalogItemId: id, catalogVersion: 8, configurationVersion: 9, expectedRevision: 0, quantity: '1.123456', unitPrice: '45.654321', discountPercent: '12.34' });
});
