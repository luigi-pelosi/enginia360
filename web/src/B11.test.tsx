import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import B10Administration from './B10Administration';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const id = '11111111-1111-1111-1111-111111111111';
const state = (delivery: string) => ({orderId:id, status:'AwaitingAdministrativeConfirmation', technicalClosure:{id,orderId:id},
  administrativeClosure:null, request:{id,orderId:id,status:'Pending',externalReference:null,rejectionCode:null,
    delivery:{state:delivery,attempts:1,failures:4,lastError:'unavailable',nextAttemptAt:null}}});
const json = (body:unknown, status=200) => Promise.resolve(new Response(JSON.stringify(body), {status}));

test('uncertain and escalated delivery remain blocked; reconciliation is explicit and retries the same command after a lost response', async () => {
  let delivery = 'Uncertain';
  const posts: {url:string; id:string}[] = [];
  vi.stubGlobal('fetch', (url:string, init?:RequestInit) => {
    if (init?.method === 'POST') {
      posts.push({url, ...JSON.parse(init.body as string)});
      if (posts.length === 1) return Promise.reject(new Error('lost'));
      delivery = 'Uncertain'; return json({replayed:true});
    }
    return json(state(delivery));
  });
  render(<B10Administration orderId={id} revision={2} token="synthetic"/>);
  await screen.findByText(/esito incerto/);
  expect((screen.getByRole('button',{name:'Chiudi amministrativamente'}) as HTMLButtonElement).disabled).toBe(true);
  delivery = 'NeedsReconciliation';
  fireEvent.click(screen.getByRole('button',{name:'Rileggi stato amministrativo'}));
  await screen.findByText(/tentativi automatici esauriti/);
  const recover = screen.getByRole('button',{name:'Verifica e riprendi richiesta'});
  await waitFor(() => expect((recover as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(recover);
  await screen.findByRole('alert');
  fireEvent.click(recover);
  await screen.findByText(/esito incerto/);
  expect(posts).toHaveLength(2);
  expect(posts[0].id).toBe(posts[1].id);
  expect(posts[0].url).toBe(`/api/v1/workshop/orders/${id}/administrative-requests/${id}/reconciliation`);
  expect(screen.queryByText(/Confermata/)).toBeNull();
});
