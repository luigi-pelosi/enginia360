import { beforeEach, afterEach, expect, test, vi } from 'vitest';
beforeEach(() => vi.stubEnv('VITE_B04_TEST_UI','false'));
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules(); });
async function openCounterparty(extra: unknown[]) {
    vi.stubEnv('VITE_B03_TEST_UI','true');
    const replies:unknown[]=[{accessToken:'synthetic-token'},[{legalEntityId:'11111111-1111-1111-1111-111111111101',legalEntityName:'Società sintetica A'}],[cp], ...extra];
    const fetchMock=vi.fn().mockImplementation(async()=>{const reply=replies.shift(); return {ok:true,json:async()=>reply};});
    vi.stubGlobal('fetch',fetchMock);
    const {default:App}=await import('./App'); render(<App/>);
    fireEvent.change(screen.getByLabelText('Utente sintetico'),{target:{value:'operatore'}});
    fireEvent.change(screen.getByLabelText('Password sintetica'),{target:{value:'synthetic-password'}});
    fireEvent.click(screen.getByRole('button',{name:'Accedi'}));
    fireEvent.click(await screen.findByRole('button',{name:'Società sintetica A'}));
    await screen.findByText(cp.legalName);
    return fetchMock;
}
test('B03 creates and rereads a company-private destination',async()=>{
    const dest={id:'11111111-4444-0000-0000-000000000001',counterpartyId:cp.id,ownerLegalEntityId:'11111111-1111-1111-1111-111111111101',address:'Destinazione sintetica UI',published:false};
    const fetchMock=await openCounterparty([[],dest,[dest]]);
    fireEvent.click(screen.getByRole('button',{name:'Destinazioni'}));
    fireEvent.change(await screen.findByLabelText('Indirizzo operativo'),{target:{value:dest.address}});
    fireEvent.click(screen.getByRole('button',{name:'Aggiungi destinazione privata'}));
    expect(await screen.findByText(dest.address)).toBeTruthy();
    expect(screen.getByText('Riservata alla società proprietaria')).toBeTruthy();
    expect(fetchMock.mock.calls[4][1].method).toBe('POST');
});
test('B03 publication is an explicit action and rereads shared state',async()=>{
    const dest={id:'11111111-4444-0000-0000-000000000001',counterpartyId:cp.id,ownerLegalEntityId:'11111111-1111-1111-1111-111111111101',address:'Pubblicazione UI',published:false};
    const fetchMock=await openCounterparty([[dest],{...dest,published:true},[{...dest,published:true}]]);
    fireEvent.click(screen.getByRole('button',{name:'Destinazioni'}));
    fireEvent.click(await screen.findByRole('button',{name:'Condividi nel tenant'}));
    expect(await screen.findByText('Condivisa nel tenant')).toBeTruthy();
    expect(fetchMock.mock.calls[4][0]).toBe(`/api/v1/counterparties/destinations/${dest.id}/publication`);
    expect(JSON.parse(fetchMock.mock.calls[4][1].body)).toEqual({legalEntityId:dest.ownerLegalEntityId});
});
test('B03 common editing uses a separate explicit command',async()=>{
    const saved={...cp,legalName:'Ragione sociale aggiornata'};
    const fetchMock=await openCounterparty([saved,[saved]]);
    fireEvent.click(screen.getByRole('button',{name:'Modifica campi comuni'}));
    fireEvent.change(screen.getByLabelText('Ragione sociale comune'),{target:{value:saved.legalName}});
    fireEvent.click(screen.getByRole('button',{name:'Salva campi comuni'}));
    expect(await screen.findByText(saved.legalName)).toBeTruthy();
    expect(fetchMock.mock.calls[3][1].method).toBe('PUT');
});
test('B03 rejects malformed server company contracts with a recoverable error',async()=>{
    vi.stubEnv('VITE_B03_TEST_UI','true');
    vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({accessToken:'synthetic-token'})}).mockResolvedValueOnce({ok:true,json:async()=>[{legalEntityId:'invalid-company'}]}));
    const {default:App}=await import('./App'); render(<App/>);
    fireEvent.change(screen.getByLabelText('Utente sintetico'),{target:{value:'operatore'}});
    fireEvent.change(screen.getByLabelText('Password sintetica'),{target:{value:'synthetic-password'}});
    fireEvent.click(screen.getByRole('button',{name:'Accedi'}));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByRole('button',{name:'Accedi'})).toBeTruthy();
});
test('B03 ignores a stale company read failure after context switching',async()=>{
    vi.stubEnv('VITE_B03_TEST_UI','true');
    let finish!:(value:unknown)=>void;
    const pending=new Promise(resolve=>{finish=resolve;});
    const fetchMock=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({accessToken:'synthetic-token'})})
      .mockResolvedValueOnce({ok:true,json:async()=>[{legalEntityId:'11111111-1111-1111-1111-111111111101',legalEntityName:'Società A'},{legalEntityId:'11111111-1111-1111-1111-111111111102',legalEntityName:'Società B'}]})
      .mockReturnValueOnce(pending).mockResolvedValueOnce({ok:true,json:async()=>[cp]});
    vi.stubGlobal('fetch',fetchMock);
    const {default:App}=await import('./App');render(<App/>);
    fireEvent.change(screen.getByLabelText('Utente sintetico'),{target:{value:'operatore'}});
    fireEvent.change(screen.getByLabelText('Password sintetica'),{target:{value:'synthetic-password'}});
    fireEvent.click(screen.getByRole('button',{name:'Accedi'}));
    fireEvent.click(await screen.findByRole('button',{name:'Società A'}));
    fireEvent.click(screen.getByRole('button',{name:'Società B'}));
    await screen.findByText(cp.legalName);
    finish({ok:false});
    await new Promise(resolve=>setTimeout(resolve,20));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('Società selezionata: Società B')).toBeTruthy();
});
const cp = { id:'11111111-3333-0000-0000-000000000001',tenantId:'11111111-1111-1111-1111-111111111111',legalName:'Controparte sintetica', fiscalIdentifier:'SYNTHETIC',registeredOffice:'Sede sintetica' };
test('private B03 login selects company and reads shared counterparty identity', async () => {
    vi.stubEnv('VITE_B03_TEST_UI','true');
    const fetchMock = vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({accessToken:'synthetic-token'})})
      .mockResolvedValueOnce({ok:true,json:async()=>[{legalEntityId:'11111111-1111-1111-1111-111111111101',legalEntityName:'Società sintetica A'}]})
      .mockResolvedValueOnce({ok:true,json:async()=>[cp]});
    vi.stubGlobal('fetch',fetchMock);
    const {default:App}=await import('./App'); render(<App/>);
    expect(screen.getByRole('heading',{name:'Controparti · prova privata B03'})).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Utente sintetico'),{target:{value:'operatore'}});
    fireEvent.change(screen.getByLabelText('Password sintetica'),{target:{value:'synthetic-password'}});
    fireEvent.click(screen.getByRole('button',{name:'Accedi'}));
    fireEvent.click(await screen.findByRole('button',{name:'Società sintetica A'}));
    expect(await screen.findByText('Controparte sintetica')).toBeTruthy();
    expect(screen.getByText('SYNTHETIC')).toBeTruthy();
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/counterparties/companies');
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/counterparties?legalEntityId=11111111-1111-1111-1111-111111111101');
});
