import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import MasterAuthority from './MasterAuthority';
const id='11111111-1111-4111-8111-111111111111';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('authorized local common edit writes once then renders authoritative reread, never optimistic saved state',async()=>{
 let saved=false; const writes:RequestInit[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options:RequestInit)=>{
  if(path==='/auth/csrf') return new Response('{"requestToken":"fresh"}');
  if(options.method==='PUT') { writes.push(options);saved=true;return new Response('{"state":"applied"}'); }
  if(path.includes('/authority?')) return new Response(JSON.stringify({state:'local',canEdit:true,version:2,sourceId:id,profileId:id,direction:'Enginia360ToExternal'}));
  return new Response(JSON.stringify({state:'ready',authority:{state:'local',canEdit:true,version:2,sourceId:id,profileId:id,direction:'Enginia360ToExternal'},revision:saved?1:0,counterparty:{id,legalName:saved?'Saved server':'Before',fiscalIdentifier:'SYNTHETIC',registeredOffice:'Office'}}));
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
