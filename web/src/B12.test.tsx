import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import B12Invoice from './B12Invoice';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const id = '11111111-1111-1111-1111-111111111111';
const summary = {orderId:id,payerId:id,revision:2,lines:[{id,catalogLabel:'Manodopera',quantity:'1',netAmount:'74.250000'}],
  netAmount:'74.250000',taxAmount:'16.335000',total:'90.585000',currency:'EUR',policy:'Case001'};
const draft = {id,orderId:id,reference:'FV-001/2026',status:'Draft',summary,issuer:null,recipient:null,confirmedAt:null};
const confirmed = {...draft,status:'Confirmed',issuer:{legalName:'Società sintetica Alfa S.r.l.'},recipient:{legalName:'Cliente sintetico'},confirmedAt:'2026-10-20T00:00:00Z'};
const json = (body: unknown, status=200) => Promise.resolve(new Response(JSON.stringify(body),{status}));
const props = {orderId:id,token:'synthetic',documentTypeId:id,configurationVersion:1,documentDate:'2026-10-20'};

test('retries the same draft command after a lost response and confirms the immutable summary', async () => {
  const commands: Record<string,unknown>[]=[]; let create=0;
  vi.stubGlobal('fetch', (_url:string, init?:RequestInit) => {
    if (init?.body) commands.push(JSON.parse(init.body as string));
    if (++create === 1) return Promise.reject(new Error('lost'));
    return json(create === 2 ? draft : confirmed, create === 2 ? 200 : 201);
  });
  render(<B12Invoice {...props}/>);
  const createButton=screen.getByRole('button',{name:'Crea bozza tecnica'});
  fireEvent.click(createButton);
  await screen.findByText(/Operazione non confermata/);
  fireEvent.click(createButton);
  await screen.findByText('Bozza tecnica creata');
  expect(commands[1].id).toBe(commands[0].id);
  expect(screen.getByText(/Totale 90.585000 EUR/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Conferma documento interno'}));
  await screen.findByText('Documento interno confermato');
  expect(screen.getByText(/Emittente Società sintetica Alfa/)).toBeTruthy();
  expect(screen.getByText(/Manodopera: 1 · 74.250000 EUR/)).toBeTruthy();
});

test('malformed responses are rejected and never shown as success', async () => {
  vi.stubGlobal('fetch', () => json({...draft,summary:{...summary,currency:'USD'}}));
  render(<B12Invoice {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Crea bozza tecnica'}));
  await screen.findByText(UNCONFIRMED_TEXT());
  expect(screen.queryByText('Bozza tecnica creata')).toBeNull();
});
function UNCONFIRMED_TEXT(){ return 'Operazione non confermata. Rileggi oppure riprova lo stesso tentativo.'; }
