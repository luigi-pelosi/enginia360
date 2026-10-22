import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import CreateOrder from './CreateOrder';
const id='11111111-1111-4111-8111-111111111111';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
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
