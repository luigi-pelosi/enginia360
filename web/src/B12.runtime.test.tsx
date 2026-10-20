import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import B12Invoice from './B12Invoice';
const base=import.meta.env.VITE_B12_HTTP_BASE as string|undefined;
const order=import.meta.env.VITE_B12_ORDER as string|undefined;
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const enabled=base&&order?test:test.skip;
enabled('real HTTP DOM creates and confirms one internal technical invoice',async()=>{
  const real=globalThis.fetch;
  const login=await real(new URL('/api/v1/development/login',base).href,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'operatore-alfa-sintetico',password:'synthetic-alpha-password'})});
  expect(login.status).toBe(200);
  const {accessToken}=await login.json() as {accessToken:string};
  vi.stubGlobal('fetch',(url:string|URL|Request,init?:RequestInit)=>real(new URL(String(url),base).href,init));
  render(<B12Invoice orderId={order!} token={accessToken} documentTypeId="11111111-7777-0000-0000-000000000010"
    configurationVersion={1} documentDate="2026-10-20"/>);
  const create=screen.getByRole('button',{name:'Crea bozza tecnica'});
  fireEvent.click(create);
  await screen.findByText('Bozza tecnica creata');
  expect(screen.getByText(/Totale 90.585000 EUR/)).toBeTruthy();
  const confirm=screen.getByRole('button',{name:'Conferma documento interno'});
  await waitFor(()=>expect((confirm as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(confirm);
  await screen.findByText('Documento interno confermato');
  expect(screen.getByText(/Emittente Società sintetica Alfa S.r.l./)).toBeTruthy();
  expect(screen.getAllByRole('listitem')).toHaveLength(1);
});
