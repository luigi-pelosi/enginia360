import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import MasterAuthority from './MasterAuthority';
const id='11111111-1111-4111-8111-111111111111';
test('supplier role uses shared revision with common edit and replays the exact dropped command before authoritative reread',async()=>{
 let revision=0, isSupplier=false, dropped=false;
 const writes:{path:string;body:string}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
  if(path==='/auth/csrf') return new Response('{"requestToken":"fresh"}');
  if(options.method==='PUT') {
   const body=options.body as string, command=JSON.parse(body); writes.push({path,body});
   if(path.endsWith('/supplier-role') && !dropped) {expect(command.expectedRevision).toBe(0);revision++;isSupplier=true;dropped=true;throw new TypeError('response dropped');}
   if(writes.length===2) {expect(body).toBe(writes[0].body);return new Response('{"state":"replayed"}');}
   expect(command.expectedRevision).toBe(revision);revision++;if(path.endsWith('/supplier-role'))isSupplier=command.isSupplier;
   return new Response('{"state":"applied"}');
  }
  return new Response(JSON.stringify({state:'ready',authority:{state:'local',canEdit:true,version:2,sourceId:id,profileId:id,direction:'Enginia360ToExternal'},revision,counterparty:{id,legalName:'Before',fiscalIdentifier:'SYNTHETIC',registeredOffice:'Office',isSupplier}}));
 }));
 await act(async()=>{render(<MasterAuthority companyId={id} counterpartyId={id} onError={vi.fn()}/>);});
 fireEvent.click(await screen.findByRole('checkbox',{name:'Ruolo fornitore'}));
 fireEvent.click(screen.getByRole('button',{name:'Salva ruolo fornitore'}));
 await screen.findByText('Esito modifica incerto: riprova solo il comando identico.');
 expect((screen.getByRole('checkbox',{name:'Ruolo fornitore'}) as HTMLInputElement).disabled).toBe(true);
 expect((screen.getByRole('button',{name:'Salva dati comuni'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Riprova ruolo identico'}));
 await screen.findByText('Dati comuni salvati e riletti — revisione 1');
 expect((screen.getByRole('checkbox',{name:'Ruolo fornitore'}) as HTMLInputElement).checked).toBe(true);
 fireEvent.change(screen.getByLabelText('Denominazione comune'),{target:{value:'Renamed'}});
 fireEvent.click(screen.getByRole('button',{name:'Salva dati comuni'}));
 await screen.findByText('Dati comuni salvati e riletti — revisione 2');
 fireEvent.click(screen.getByRole('checkbox',{name:'Ruolo fornitore'}));
 fireEvent.click(screen.getByRole('button',{name:'Salva ruolo fornitore'}));
 await screen.findByText('Dati comuni salvati e riletti — revisione 3');
 expect(JSON.parse(writes[0].body)).toMatchObject({legalEntityId:id,authorityVersion:2,expectedRevision:0,isSupplier:true});
 expect(writes).toHaveLength(4);
});
test.each(['external','missing','denied'])('supplier role remains visible read-only with %s authority or grant',async(state)=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({state:'ready',revision:7,authority:state==='missing'?{state:'missing',canEdit:false}:{state:state==='external'?'external':'local',canEdit:state!=='denied',version:2,sourceId:id,profileId:id,direction:state==='external'?'ExternalToEnginia360':'Enginia360ToExternal'},counterparty:{id,legalName:'Historical',fiscalIdentifier:'SYNTHETIC',registeredOffice:'Office',isSupplier:true}}))));
 await act(async()=>{render(<MasterAuthority companyId={id} counterpartyId={id} onError={vi.fn()}/>);});
 const control=await screen.findByRole('checkbox',{name:'Ruolo fornitore'}) as HTMLInputElement;
 expect(control.checked).toBe(true);expect(control.disabled).toBe(true);
 expect(screen.queryByRole('button',{name:'Salva ruolo fornitore'})).toBeNull();
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('authorized local common edit writes once then renders authoritative reread, never optimistic saved state',async()=>{
 let saved=false; const writes:RequestInit[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
  if(path==='/auth/csrf') return new Response('{"requestToken":"fresh"}');
  if(options.method==='PUT') { writes.push(options);saved=true;return new Response('{"state":"applied"}'); }
  if(path.includes('/authority?')) return new Response(JSON.stringify({state:'local',canEdit:true,version:2,sourceId:id,profileId:id,direction:'Enginia360ToExternal'}));
  return new Response(JSON.stringify({state:'ready',authority:{state:'local',canEdit:true,version:2,sourceId:id,profileId:id,direction:'Enginia360ToExternal'},revision:saved?1:0,counterparty:{id,legalName:saved?'Saved server':'Before',fiscalIdentifier:'SYNTHETIC',registeredOffice:'Office',isSupplier:false}}));
 }));
 await act(async()=>{render(<MasterAuthority companyId={id} counterpartyId={id} onError={vi.fn()}/>);});
 await screen.findByDisplayValue('Before');
 fireEvent.change(screen.getByLabelText('Denominazione comune'),{target:{value:'New explicit name'}});
 fireEvent.click(screen.getByRole('button',{name:'Salva dati comuni'}));
 await screen.findByDisplayValue('Saved server');
 expect(writes).toHaveLength(1);expect(writes[0].method).toBe('PUT');
 expect(JSON.parse(writes[0].body as string)).toMatchObject({authorityVersion:2,expectedRevision:0,legalName:'New explicit name'});
 expect(screen.getByText('Dati comuni salvati e riletti — revisione 1')).toBeTruthy();
});
