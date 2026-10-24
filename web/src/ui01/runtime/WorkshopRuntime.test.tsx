import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import WorkshopRuntime from './WorkshopRuntime';
import { id, order, summary, policy, capabilities, editorView } from './editorFixtures';
export { order, summary, policy, capabilities, editorView };
export function server(overrides: Record<string, unknown> = {}) {
  const routes: Record<string, unknown> = { '/auth/session': { authenticated: true }, '/auth/csrf': { requestToken: 'test-only' }, '/api/v1/organization/contexts': [], '/api/v1/workshop/contexts': [], ['/api/v1/workshop/orders/'+id+'/editor']: editorView, ...overrides };
  const fetch = vi.fn(async (path: string, _options?: RequestInit) => new Response(JSON.stringify(routes[path] ?? []))); vi.stubGlobal('fetch', fetch); return fetch;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ''; });
test('known UUID URL reopens server order even with empty create scopes; immutable q6 and disabled R03 controls', async () => {
  window.location.hash = 'order='+id; server(); render(<WorkshopRuntime />);
  expect(await screen.findByText('Intestatario: '+order.vehicleHolderId)).toBeTruthy();
  expect(screen.getByText('Configurazione documento: 7')).toBeTruthy();
  expect(screen.getByText('Società: '+order.legalEntityId)).toBeTruthy();
  expect(await screen.findByText('0.000000 EUR')).toBeTruthy();
  expect(screen.getByText(/Documento v7 · Policy righe v9 · Struttura v1 · Revisione 0/)).toBeTruthy();
  for (const name of ['Cambia testata', 'Cambia pagante', 'Cambia veicolo']) expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(true);
  for (const name of ['Prenotazione','Prelievo','Preparazione','Installazione / consumo','Carcassa','Esito amministrativo esterno']) expect(screen.getByText(name)).toBeTruthy();
  expect(screen.queryByText('Non collegato in UI01.b')).toBeNull();
  expect(screen.getAllByText('Disponibile nel pannello Chiusura e attesa amministrativa').length).toBe(1);
  expect(screen.getAllByText('Disponibile nel pannello Materiali').length).toBe(5);
  fireEvent.click(screen.getByRole('button', { name: 'Rileggi commessa' }));
  expect(await screen.findByText('Valori salvati riletti — revisione 0')).toBeTruthy();
});
test('server selectors and non-default document version create with independent payer and vehicle', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(id);
  const fetch = server({ '/api/v1/workshop/contexts': [{ legalEntityId: id, legalEntityName: 'Società sintetica', siteId: id, siteName: 'Sede sintetica' }],
    ['/api/v1/workshop/document-types?legalEntityId='+id+'&siteId='+id]: [{ id, name: 'Ordine server', version: 7, directCreationEnabled: true }],
    ['/api/v1/workshop/vehicles?legalEntityId='+id+'&siteId='+id+'&search=&limit=20']: [{ id, label: 'Veicolo server' }],
    ['/api/v1/counterparties?legalEntityId='+id+'&search=&limit=20']: [{ id, legalName: 'Pagante server' }], '/api/v1/workshop/orders': order });
  render(<WorkshopRuntime />);
  await screen.findByRole('option', { name: 'Ordine server · v7' });
  await screen.findByRole('option', { name: 'Pagante server' });
  await screen.findByRole('option', { name: 'Veicolo server' });
  fireEvent.change(screen.getByLabelText('Tipo documento'), { target: { value: id } });
  fireEvent.change(screen.getByLabelText('Pagante'), { target: { value: id } });
  fireEvent.change(screen.getByLabelText('Veicolo'), { target: { value: id } });
  expect((screen.getByLabelText('Pagante') as HTMLSelectElement).value).toBe(id);
  fireEvent.click(screen.getByRole('button', { name: 'Crea commessa' }));
  await screen.findByText('Valori salvati riletti — revisione 0');
  const call = fetch.mock.calls.find(([p, options]) => p === '/api/v1/workshop/orders' && options?.method === 'POST');
  expect(JSON.parse(call![1]!.body as string)).toMatchObject({ configurationVersion: 7, payerId: id, vehicleId: id });
});
test('loaded order binds actual add form; session expiry clears document and prevents writes', async () => {
  window.location.hash = 'order='+id;
  const fetch = server(); render(<WorkshopRuntime />);
  await screen.findByLabelText('Workspace commessa');
  fetch.mockImplementation(async (path: string) => path === '/auth/session' ? new Response('{"authenticated":false}') : new Response(null, { status: 401 }));
  fireEvent.click(screen.getByRole('button', { name: 'Riprova sessione' }));
  await screen.findByText('Sessione terminata. Accedi nuovamente.');
  expect(screen.queryByText('Intestatario: '+order.vehicleHolderId)).toBeNull();
  expect(screen.queryByRole('button', { name: 'Crea commessa' })).toBeNull();
});
test('anonymous browser gets native antiforgery login without synthetic credentials', async () => {
  server({ '/auth/session': { authenticated: false } }); render(<WorkshopRuntime />);
  const login = await screen.findByRole('button', { name: 'Accedi' });
  const form = login.closest('form')!; expect(form.getAttribute('action')).toBe('/auth/login');
  expect(form.querySelector('input')!.value).toBe('test-only');
});
test('own organization capability unknown stays unknown and never gates Workshop using canWrite', async () => {
  server({ '/api/v1/organization/contexts': [{ tenantId: id, tenantName: 'Tenant sintetico', legalEntityId: id, legalEntityName: 'Società', siteId: id, siteName: 'Sede', warehouseId: id, warehouseName: 'Magazzino', readPermission: 'organization-context.read', capability: 'organization-context', capabilityEnabled: null, canWrite: false }] });
  render(<WorkshopRuntime />);
  expect(await screen.findByText(/organization-context: Non configurata/)).toBeTruthy();
  expect(screen.getByText(/canWrite riguarda solo/)).toBeTruthy();
});
test('late authenticated response cannot restore authority after newer anonymous session check', async () => {
  let resolve!: (r: Response) => void;
  const delayed = new Promise<Response>(r => { resolve = r; });
  let count = 0; const fetch = server();
  fetch.mockImplementation(async (path: string) => path === '/auth/session' ? (++count === 1 ? delayed : new Response('{"authenticated":false}')) : path === '/auth/csrf' ? new Response('{"requestToken":"test-only"}') : new Response('[]'));
  render(<WorkshopRuntime />);
  fireEvent.click(screen.getByRole('button', { name: 'Riprova sessione' }));
  await screen.findByRole('button', { name: 'Accedi' });
  await act(async () => { resolve(new Response('{"authenticated":true}')); await new Promise(r => setTimeout(r, 30)); });
  expect(screen.queryByRole('heading', { name: 'Nuova commessa' })).toBeNull();
});
test('accepted command followed by failed read is visibly unverified; reread never resubmits the write', async () => {
  window.location.hash='order='+id; let written=false, outage=true;
  const fetch=server();
  fetch.mockImplementation(async(path:string,options?:RequestInit)=>{
    if(options?.method==='POST'){written=true;const b=JSON.parse(options.body as string);return new Response(JSON.stringify({commandId:b.commandId,orderId:id,appliedRevision:1,resultKind:'Created',targetId:b.groupId}));}
    if(path.endsWith('/editor')) return written && outage ? new Response(null,{status:503}) : new Response(JSON.stringify(editorView));
    return new Response(JSON.stringify(path==='/auth/session'?{authenticated:true}:path==='/auth/csrf'?{requestToken:'test-only'}:[]));
  });
  render(<WorkshopRuntime/>); await screen.findByLabelText('Workspace commessa');
  fireEvent.change(screen.getByLabelText('Nuova lavorazione'),{target:{value:'Freni'}});
  fireEvent.click(screen.getByRole('button',{name:'Aggiungi lavorazione'}));
  await screen.findAllByText(/Scrittura accettata; riepilogo non verificato/);
  expect(screen.queryByText('0.000000 EUR')).toBeNull();
  expect(screen.queryByRole('button',{name:'Crea commessa'})).toBeNull();
  outage=false; fireEvent.click(screen.getByRole('button',{name:'Rileggi commessa'}));
  await screen.findByText('Valori salvati riletti — revisione 0');
  expect(fetch.mock.calls.filter(([,o])=>o?.method==='POST')).toHaveLength(1);
});
test('read-only order success is not overwritten by independently denied catalog selector',async()=>{
 window.location.hash='order='+id; const fetch=server();
 fetch.mockImplementation(async(path:string)=>path.includes('/catalog?')?new Response(null,{status:403}):new Response(JSON.stringify(path==='/auth/session'?{authenticated:true}:path==='/auth/csrf'?{requestToken:'test-only'}:path.endsWith('/editor')?editorView:[])));
 render(<WorkshopRuntime/>);
 await screen.findByText(/Catalogo non disponibile/);
 expect(screen.getByText('Valori salvati riletti — revisione 0')).toBeTruthy();
 expect(screen.getByText('0.000000 EUR')).toBeTruthy();
});
test('pending catalog response cannot restore choices after session expiry',async()=>{
 window.location.hash='order='+id; let expired=false, release!:(r:Response)=>void;
 const fetch=server();
 fetch.mockImplementation(async(path:string)=>{
  if(path.includes('search=late')) return await new Promise<Response>(resolve=>{release=resolve;});
  return new Response(JSON.stringify(path==='/auth/session'?{authenticated:!expired}:path==='/auth/csrf'?{requestToken:'test-only'}:path.endsWith('/editor')?editorView:[]));
 });
 render(<WorkshopRuntime/>); await screen.findByLabelText('Workspace commessa');
 fireEvent.change(screen.getByLabelText('Ricerca articolo / prestazione'),{target:{value:'late'}});
 fireEvent.click(screen.getByRole('button',{name:'Cerca articolo / prestazione'}));
 expired=true; fireEvent.click(screen.getByRole('button',{name:'Riprova sessione'}));
 await screen.findByText('Sessione terminata. Accedi nuovamente.');
 await act(async()=>{release(new Response(JSON.stringify([{id,kind:'Service',label:'Late secret choice',version:8}])));});
 expect(screen.queryByRole('option',{name:/Late secret choice/})).toBeNull();
 expect(screen.queryByLabelText('Workspace commessa')).toBeNull();
});

test('closure panel is lazy, keeps editor, footer and sibling panels reachable, and its 401 ends the shared session', async () => {
  window.location.hash = 'order='+id; let revoked = false;
  const fetch = server();
  const closureActions = { orderId: id, commercialRevision: 0, technicalClosure: null, canReadAdministrativeState: false, canCompleteTechnical: true, canRequestAdministrative: false, mayRequestReconciliation: false, canCompleteAdministrative: false, actionReasons: [], administrativeRuntime: { kind: 'SimulatorV1', contractVersion: 1 } };
  fetch.mockImplementation(async (path: string) => path === '/api/v1/workshop/orders/'+id+'/closure-actions' ? (revoked ? new Response(null, { status: 401 }) : new Response(JSON.stringify(closureActions)))
    : path.endsWith('/technical-closure-gate') ? new Response(JSON.stringify({ orderId: id, status: 'Clear', requirements: [] }))
    : new Response(JSON.stringify(path === '/auth/session' ? { authenticated: true } : path === '/auth/csrf' ? { requestToken: 'test-only' } : path.endsWith('/editor') ? editorView : [])));
  render(<WorkshopRuntime />);
  await screen.findByLabelText('Workspace commessa');
  expect(fetch.mock.calls.some(([p]) => String(p).includes('closure-actions'))).toBe(false);
  fireEvent.click(screen.getByText('Chiusura e attesa amministrativa'));
  await screen.findByText('Requisito carcassa: Clear');
  expect(screen.getByText('Simulatore amministrativo v1 · nessun collegamento Giobby')).toBeTruthy();
  expect(screen.getByText('Operazioni materiali')).toBeTruthy(); expect(screen.getByText('Tempo effettivo mio')).toBeTruthy();
  expect(screen.getByText('0.000000 EUR')).toBeTruthy(); expect(screen.getByLabelText('Workspace commessa')).toBeTruthy();
  revoked = true; fireEvent.click(screen.getByRole('button', { name: 'Rileggi stato' }));
  await screen.findByText('Sessione terminata. Accedi nuovamente.');
  expect(screen.queryByLabelText('Workspace commessa')).toBeNull();
});
