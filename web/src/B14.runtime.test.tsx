import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import B10Administration from './B10Administration';
const base=import.meta.env.VITE_B14_HTTP_BASE as string|undefined;
const order=import.meta.env.VITE_B14_ORDER as string|undefined;
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const enabled=base&&order?test:test.skip;
enabled('real HTTP DOM shows the administratively closed external order of the joint scenario',async()=>{
  const real=globalThis.fetch;
  const login=await real(new URL('/api/v1/development/login',base).href,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'operatore-beta-sintetico',password:'synthetic-beta-password'})});
  expect(login.status).toBe(200);
  const {accessToken}=await login.json() as {accessToken:string};
  vi.stubGlobal('fetch',(url:string|URL|Request,init?:RequestInit)=>real(new URL(String(url),base).href,init));
  render(<B10Administration orderId={order!} revision={2} token={accessToken}/>);
  await screen.findByText(/Chiusa amministrativamente/);
  expect(screen.getAllByText(/elaborazione completata/).length).toBeGreaterThan(0);
  // The administrative closure is already registered: a second attempt must stay disabled, not fabricate a new one.
  const close=screen.getByRole('button',{name:'Chiudi amministrativamente'}) as HTMLButtonElement;
  expect(close.disabled).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'Rileggi stato amministrativo'}));
  await screen.findByText(/Chiusa amministrativamente/);
});
