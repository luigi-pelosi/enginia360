import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import CreateOrder from './CreateOrder';
const id='11111111-1111-4111-8111-111111111111';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('explicit vehicle search uses bounded server paging, preserves payer and exposes empty/retry states',async()=>{
 const calls:string[]=[]; let unavailable=false;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{
  calls.push(path);
  if(path.includes('/vehicles') && unavailable) return new Response(null,{status:503});
  const value=path.endsWith('/contexts')?[{legalEntityId:id,legalEntityName:'Company',siteId:id,siteName:'Site'}]:path.includes('/document-types')?[{id,name:'Type',version:7,directCreationEnabled:true}]:path.includes('/vehicles')?(path.includes('search=empty')?[]:Array.from({length:20},(_,i)=>({id:`11111111-1111-4111-8111-${String(i+1).padStart(12,'0')}`,label:'Vehicle '+i}))):[{id,legalName:'Payer'}];
  return new Response(JSON.stringify(value));
 }));
 await act(async()=>{render(<CreateOrder onCreated={vi.fn()} onError={vi.fn()}/>);});
 await screen.findByRole('option',{name:'Payer'});
 fireEvent.change(screen.getByLabelText('Pagante'),{target:{value:id}});
 const before=calls.length;
 fireEvent.change(screen.getByLabelText('Ricerca veicolo'),{target:{value:'empty'}});
 expect(calls.length).toBe(before);
 fireEvent.click(screen.getByRole('button',{name:'Cerca veicolo'}));
 await screen.findByText('Veicolo: nessun risultato.');
 expect((screen.getByLabelText('Pagante') as HTMLSelectElement).value).toBe(id);
 fireEvent.change(screen.getByLabelText('Ricerca veicolo'),{target:{value:''}});
 fireEvent.click(screen.getByRole('button',{name:'Cerca veicolo'}));
 await screen.findByRole('option',{name:'Vehicle 19'});
 fireEvent.click(screen.getByRole('button',{name:'Pagina successiva veicolo'}));
 await act(async()=>{});
 expect(calls.some(p=>p.includes('/vehicles') && p.includes('limit=20') && p.includes('after=11111111-1111-4111-8111-000000000020'))).toBe(true);
 unavailable=true; fireEvent.click(screen.getByRole('button',{name:'Cerca veicolo'}));
 await screen.findByText(/Veicolo: Servizio non disponibile/);
 expect(screen.queryByRole('option',{name:'Vehicle 19'})).toBeNull();
 unavailable=false; fireEvent.click(screen.getByRole('button',{name:'Cerca veicolo'}));
 await screen.findByRole('option',{name:'Vehicle 19'});
});
test('payer search response is discarded after clearing the company context',async()=>{
 let release!: (response: Response)=>void;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{
  if(path.includes('search=late')) return await new Promise<Response>(resolve=>{release=resolve;});
  const value=path.endsWith('/contexts')?[{legalEntityId:id,legalEntityName:'Company',siteId:id,siteName:'Site'}]:path.includes('/document-types')?[{id,name:'Type',version:7,directCreationEnabled:true}]:path.includes('/vehicles')?[{id,label:'Vehicle'}]:[{id,legalName:'Payer'}];
  return new Response(JSON.stringify(value));
 }));
 await act(async()=>{render(<CreateOrder onCreated={vi.fn()} onError={vi.fn()}/>);});
 await screen.findByRole('option',{name:'Payer'});
 fireEvent.change(screen.getByLabelText('Ricerca pagante'),{target:{value:'late'}});
 fireEvent.click(screen.getByRole('button',{name:'Cerca pagante'}));
 fireEvent.change(screen.getByLabelText('Società / sede'),{target:{value:''}});
 await act(async()=>{release(new Response(JSON.stringify([{id,legalName:'Late previous company'}])));});
 expect(screen.queryByRole('option',{name:'Late previous company'})).toBeNull();
});
test('same-company site switch invalidates an outstanding payer search',async()=>{
 let release!: (response: Response)=>void;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{
  if(path.includes('search=late')) return await new Promise<Response>(resolve=>{release=resolve;});
  const value=path.endsWith('/contexts')?[{legalEntityId:id,legalEntityName:'Company',siteId:id,siteName:'Site A'},{legalEntityId:id,legalEntityName:'Company',siteId:'22222222-2222-4222-8222-222222222222',siteName:'Site B'}]:path.includes('/document-types')?[{id,name:'Type',version:7,directCreationEnabled:true}]:path.includes('/vehicles')?[{id,label:'Vehicle'}]:[{id,legalName:'Payer'}];
  return new Response(JSON.stringify(value));
 }));
 await act(async()=>{render(<CreateOrder onCreated={vi.fn()} onError={vi.fn()}/>);});
 await screen.findByRole('option',{name:'Payer'});
 fireEvent.change(screen.getByLabelText('Ricerca pagante'),{target:{value:'late'}});
 fireEvent.click(screen.getByRole('button',{name:'Cerca pagante'}));
 fireEvent.change(screen.getByLabelText('Società / sede'),{target:{value:'1'}});
 await act(async()=>{release(new Response(JSON.stringify([{id,legalName:'Late previous site'}])));});
 expect(screen.queryByRole('option',{name:'Late previous site'})).toBeNull();
});
test('older context refresh cannot restore a superseded company',async()=>{
 let count=0, release!:(r:Response)=>void;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{
  if(path.endsWith('/contexts')) {
   if(++count===1) return await new Promise<Response>(resolve=>{release=resolve;});
   return new Response(JSON.stringify([{legalEntityId:id,legalEntityName:'New company',siteId:id,siteName:'New site'}]));
  }
  return new Response('[]');
 }));
 render(<CreateOrder onCreated={vi.fn()} onError={vi.fn()}/>);
 fireEvent.click(screen.getByRole('button',{name:'Aggiorna contesti'}));
 await screen.findByRole('option',{name:'New company / New site'});
 await act(async()=>{release(new Response(JSON.stringify([{legalEntityId:id,legalEntityName:'Old company',siteId:id,siteName:'Old site'}])));});
 expect(screen.queryByRole('option',{name:'Old company / Old site'})).toBeNull();
});
test('definitive version conflict releases exact pending command and offers current configuration reload',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(options?.method==='POST')return new Response(null,{status:409});
  const value=path==='/auth/csrf'?{requestToken:'test-only'}:path.endsWith('/contexts')?[{legalEntityId:id,legalEntityName:'Company',siteId:id,siteName:'Site'}]:path.includes('/document-types')?[{id,name:'Type',version:7,directCreationEnabled:true}]:path.includes('/vehicles')?[{id,label:'Vehicle'}]:[{id,legalName:'Payer'}];return new Response(JSON.stringify(value));
 }));
 await act(async()=>{ render(<CreateOrder onCreated={vi.fn()} onError={vi.fn()}/>); });
 await screen.findByRole('option',{name:'Type · v7'});
 for(const label of ['Tipo documento','Pagante','Veicolo'])fireEvent.change(screen.getByLabelText(label),{target:{value:id}});
 fireEvent.click(screen.getByRole('button',{name:'Crea commessa'}));
 await screen.findByText(/Conflitto/);
 expect((screen.getByRole('button',{name:'Aggiorna contesti'}) as HTMLButtonElement).disabled).toBe(false);
 expect(screen.queryByRole('button',{name:'Riprova comando identico'})).toBeNull();
});
