import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import B13JournalEntry from './B13JournalEntry';
const base=import.meta.env.VITE_B13_HTTP_BASE as string|undefined;
const invoice=import.meta.env.VITE_B13_INVOICE as string|undefined;
const entry=import.meta.env.VITE_B13_ENTRY as string|undefined;
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const enabled=base&&invoice&&entry?test:test.skip;
enabled('real HTTP DOM rereads the balanced technical journal entry of the confirmed invoice',async()=>{
  const real=globalThis.fetch;
  const login=await real(new URL('/api/v1/development/login',base).href,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'operatore-alfa-sintetico',password:'synthetic-alpha-password'})});
  expect(login.status).toBe(200);
  const {accessToken}=await login.json() as {accessToken:string};
  vi.stubGlobal('fetch',(url:string|URL|Request,init?:RequestInit)=>real(new URL(String(url),base).href,init));
  render(<B13JournalEntry invoiceId={invoice!} token={accessToken} chartVersion={1} entryId={entry}/>);
  fireEvent.click(screen.getByRole('button',{name:'Rileggi registrazione'}));
  await screen.findByText(/Dare 200.690000 = Avere 200.690000 EUR/);
  expect(screen.getByText(/differenza 0.000000/)).toBeTruthy();
  expect(screen.getByText(/collegata alla fattura confermata/)).toBeTruthy();
  expect(screen.getAllByRole('row')).toHaveLength(4);
  // A second posting attempt on the already posted invoice must be refused without touching the invoice.
  fireEvent.click(screen.getByRole('button',{name:'Registra scrittura'}));
  await screen.findByText(/la fattura confermata resta invariata/);
});
