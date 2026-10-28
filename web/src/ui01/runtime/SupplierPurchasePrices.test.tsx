import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorkshopRuntime from './WorkshopRuntime';
import SupplierPurchasePrices from './SupplierPurchasePrices';
import { id, editorView } from './editorFixtures';
function server() {
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>new Response(JSON.stringify(path==='/auth/session'?{authenticated:true}:path==='/auth/csrf'?{requestToken:'test-only'}:path.endsWith('/editor')?editorView:[]))));
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();window.location.hash='';});
test('purchase-list maintenance is a lazy Italian explicit-read surface in the existing company workspace',async()=>{
 window.location.hash='order='+id;server();render(<WorkshopRuntime/>);
 await screen.findByLabelText('Workspace commessa');
 fireEvent.click(screen.getByText('Listini acquisto fornitori',{exact:true}));
 expect(await screen.findByLabelText('UUID fornitore listino')).toBeTruthy();
 expect(screen.getByLabelText('UUID articolo listino')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Rileggi listino'})).toBeTruthy();
});
const state = (entry: null | {revision:number;unitPurchasePrice:string}, canManage=true) => ({state:'ready',entry,history:entry?[entry]:[],revision:entry?.revision??0,requiresManualPrice:!entry,provisionalUnitPurchasePrice:entry?null:'0.000000',canManage,writeState:'master_local',authorityVersion:1,supplier:{id,name:'Fornitore server',revision:2,isSupplier:true},item:{id,label:'Articolo server',version:8}});
async function selectList() {
 fireEvent.change(screen.getByLabelText('UUID fornitore listino'),{target:{value:id}});
 fireEvent.change(screen.getByLabelText('UUID articolo listino'),{target:{value:id}});
 fireEvent.click(screen.getByRole('button',{name:'Rileggi listino'}));
}
test('missing lookup displays provisional zero but never invents a stored entry or price entry',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(state(null)))));
 render(<SupplierPurchasePrices companyId={id}/>);await selectList();
 expect(await screen.findByText(/Prezzo assente.*0.000000 provvisorio/)).toBeTruthy();
 expect((screen.getByLabelText('Prezzo unitario acquisto') as HTMLInputElement).value).toBe('');
 expect(screen.getByText(/Fornitore server.*Articolo server/)).toBeTruthy();
 expect(screen.queryByText(/Revisione 1/)).toBeNull();
});
test('deliberate zero saves only on explicit click then authoritative reread distinguishes present zero',async()=>{
 let saved=false;const writes:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
  if(path==='/auth/csrf')return new Response('{"requestToken":"fresh"}');
  if(options.method==='PUT'){writes.push(options.body as string);saved=true;return new Response(JSON.stringify({state:'applied',revision:1,commandId:JSON.parse(options.body as string).commandId}));}
  return new Response(JSON.stringify(state(saved?{revision:1,unitPurchasePrice:'0.000000'}:null)));
 }));
 render(<SupplierPurchasePrices companyId={id}/>);await selectList();await screen.findByText(/Prezzo assente/);
 fireEvent.change(screen.getByLabelText('Prezzo unitario acquisto'),{target:{value:'0'}});
 expect(writes).toHaveLength(0);fireEvent.click(screen.getByRole('button',{name:'Salva prezzo acquisto'}));
 expect(await screen.findByText('Prezzo salvato e riletto — revisione 1')).toBeTruthy();
 expect(screen.getByText('Prezzo presente: 0.000000')).toBeTruthy();
 expect(writes).toHaveLength(1);expect(JSON.parse(writes[0])).toMatchObject({legalEntityId:id,expectedRevision:0,supplierRevision:2,catalogVersion:8,authorityVersion:1,unitPurchasePrice:'0'});
});
test('lost accepted price response freezes resource and ancestor context then replays exact UUID and body',async()=>{
 let dropped=false;const writes:{path:string;body:string}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
  if(path==='/auth/csrf')return new Response('{"requestToken":"fresh"}');
  if(options.method==='PUT') {writes.push({path,body:options.body as string});if(!dropped){dropped=true;throw new TypeError('dropped accepted response');}return new Response(JSON.stringify({state:'replayed',revision:1,commandId:JSON.parse(options.body as string).commandId}));}
  return new Response(JSON.stringify(path==='/auth/session'?{authenticated:true}:path.endsWith('/editor')?editorView:path.includes('/purchase-price?')?state(dropped?{revision:1,unitPurchasePrice:'12.345678'}:null):[]));
 }));
 window.location.hash='order='+id;render(<WorkshopRuntime/>);await screen.findByLabelText('Workspace commessa');
 fireEvent.click(screen.getByText('Listini acquisto fornitori',{exact:true}));await screen.findByLabelText('UUID fornitore listino');await selectList();await screen.findByText(/Prezzo assente/);
 fireEvent.change(screen.getByLabelText('Prezzo unitario acquisto'),{target:{value:'12.345678'}});
 fireEvent.click(screen.getByRole('button',{name:'Salva prezzo acquisto'}));
 await screen.findByText('Esito prezzo incerto: riprova solo il comando identico.');
 for(const label of ['UUID fornitore listino','UUID articolo listino','Prezzo unitario acquisto','UUID commessa'])expect((screen.getByLabelText(label) as HTMLInputElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Riprova prezzo identico'}));
 await screen.findByText('Prezzo salvato e riletto — revisione 1');
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0]);
 expect((screen.getByLabelText('UUID commessa') as HTMLInputElement).disabled).toBe(false);
});
test('price response uncertainty must fence ancestor order selection before another document can be opened',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
  if(path==='/auth/csrf')return new Response('{"requestToken":"fresh"}');
  if(options.method==='PUT')throw new TypeError('response dropped');
  return new Response(JSON.stringify(path==='/auth/session'?{authenticated:true}:path.endsWith('/editor')?editorView:path.includes('/purchase-price?')?state(null):[]));
 }));
 window.location.hash='order='+id;render(<WorkshopRuntime/>);await screen.findByLabelText('Workspace commessa');
 fireEvent.click(screen.getByText('Listini acquisto fornitori',{exact:true}));await screen.findByLabelText('UUID fornitore listino');await selectList();await screen.findByText(/Prezzo assente/);
 fireEvent.change(screen.getByLabelText('Prezzo unitario acquisto'),{target:{value:'0'}});fireEvent.click(screen.getByRole('button',{name:'Salva prezzo acquisto'}));
 await waitFor(()=>expect((screen.getByLabelText('UUID commessa') as HTMLInputElement).disabled).toBe(true));
});
test('accepted write with failed reread remains unverified and only read recovery unlocks editing',async()=>{
 let saved=false,outage=true,puts=0;
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
  if(path==='/auth/csrf')return new Response('{"requestToken":"fresh"}');
  if(options.method==='PUT'){saved=true;puts++;return new Response(JSON.stringify({state:'applied',revision:1,commandId:JSON.parse(options.body as string).commandId}));}
  if(saved&&outage)return new Response(null,{status:503});
  return new Response(JSON.stringify(state(saved?{revision:1,unitPurchasePrice:'0.000000'}:null)));
 }));
 render(<SupplierPurchasePrices companyId={id}/>);await selectList();await screen.findByText(/Prezzo assente/);
 fireEvent.change(screen.getByLabelText('Prezzo unitario acquisto'),{target:{value:'0'}});fireEvent.click(screen.getByRole('button',{name:'Salva prezzo acquisto'}));
 await screen.findByText('Prezzo accettato; rilettura non verificata. Rileggi il listino.');
 expect((screen.getByLabelText('UUID fornitore listino') as HTMLInputElement).disabled).toBe(true);
 outage=false;fireEvent.click(screen.getByRole('button',{name:'Rileggi listino'}));
 await screen.findByText('Prezzo salvato e riletto — revisione 1');expect(puts).toBe(1);
 expect((screen.getByLabelText('UUID fornitore listino') as HTMLInputElement).disabled).toBe(false);
});
