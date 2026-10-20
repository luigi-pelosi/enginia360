import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import B10Administration from './B10Administration';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const id = '11111111-1111-1111-1111-111111111111';
const closure = {id, orderId: id, revision: 2, closedAt: '2026-10-20T00:00:00+00:00', operatorId: id};
const summary = {orderId: id, payerId: id, revision: 2, lines: [], netAmount: '1.000000', taxAmount: '0.220000', total: '1.220000', currency: 'EUR', policy: 'Case001'};
const request = (status: string, externalReference: string | null, delivery: string) => ({id, orderId: id, legalEntityId: id, siteId: id,
  destination: 'External', destinationVersion: 1, contractVersion: 1, summary, requestedAt: '2026-10-20T00:00:00+00:00', operatorId: id,
  status, externalReference, rejectionCode: null, outcomeAt: null, delivery: {state: delivery, attempts: 1, lastAttemptAt: null, nextAttemptAt: null, lastError: null}});
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), {status}));

test('lost committed closure is reread; the same command ID is retried and received is never shown as confirmed', async () => {
  const posts: {url: string; body: Record<string, unknown>}[] = [];
  let closed = false, requested = false;
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      posts.push({url, body: JSON.parse(init.body as string)});
      if (url.endsWith('/technical-closure')) {
        if (closed) return json(closure);
        closed = true;
        return Promise.reject(new Error('lost'));
      }
      requested = true;
      return json(request('Pending', null, 'Queued'), 201);
    }
    return json({orderId: id, status: requested ? 'AwaitingAdministrativeConfirmation' : closed ? 'TechnicallyClosed' : 'Open',
      technicalClosure: closed ? closure : null, request: requested ? request('Pending', null, 'Received') : null, administrativeClosure: null});
  });
  render(<B10Administration orderId={id} revision={2} token="synthetic"/>);
  await screen.findByText('Commessa aperta: chiusura tecnica non registrata');
  const close = screen.getByRole('button', {name: 'Chiudi tecnicamente'});
  await waitFor(() => expect((close as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(close);
  await screen.findByText(/Operazione non confermata/);
  fireEvent.click(close);
  await screen.findByText('Completata tecnicamente — richiesta amministrativa da inviare');
  fireEvent.click(screen.getByRole('button', {name: 'Invia al gestionale amministrativo'}));
  await screen.findByText('Completata tecnicamente — in attesa di conferma amministrativa');
  await screen.findByText('Consegna al gestionale: ricevuta (sola acquisizione) · tentativi 1');
  expect(screen.queryByText(/Confermata/)).toBeNull();
  expect(posts.map(x => x.url.split('/').pop())).toEqual(['technical-closure', 'technical-closure', 'administrative-requests']);
  expect(posts[0].body).toEqual({id: posts[0].body.id, expectedRevision: 2});
  expect(posts[1].body.id).toBe(posts[0].body.id);
  expect(posts[2].body).toEqual({id: posts[2].body.id, expectedRevision: 2});
});

test('refusals and malformed state are explicit, never treated as success', async () => {
  let malformed = false;
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return json({code: 'technical_requirements_pending'}, 409);
    if (malformed) return json({orderId: id, status: 'AdministrativelyConfirmed', technicalClosure: closure, request: request('Confirmed', 'not a reference!', 'Completed'), administrativeClosure: null});
    return json({orderId: id, status: 'Open', technicalClosure: null, request: null, administrativeClosure: null});
  });
  render(<B10Administration orderId={id} revision={2} token="synthetic"/>);
  const close = await screen.findByRole('button', {name: 'Chiudi tecnicamente'});
  await waitFor(() => expect((close as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(close);
  await screen.findByText('Chiusura tecnica rifiutata: carcassa da rientrare. Nessuna chiusura registrata.');
  malformed = true;
  fireEvent.click(screen.getByRole('button', {name: 'Rileggi stato amministrativo'}));
  await screen.findByText('Stato amministrativo non disponibile. Rileggi prima di continuare.');
  expect(screen.queryByText(/Confermata/)).toBeNull();
});
