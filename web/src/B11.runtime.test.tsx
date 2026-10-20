import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import B10Administration from './B10Administration';
const base=import.meta.env.VITE_B10_HTTP_BASE as string|undefined;
const simulator=import.meta.env.VITE_B10_SIMULATOR as string|undefined;
const order=import.meta.env.VITE_B11_ORDER as string|undefined;
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test.skipIf(!base||!simulator||!order)('B11 real authenticated DOM shows escalation, explicitly reconciles and closes only after external business confirmation',async()=>{
 const real=globalThis.fetch;
 const login=await real(`${base}/api/v1/development/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'operatore-alfa-sintetico',password:'synthetic-alpha-password'})});
 expect(login.status).toBe(200);
 const {accessToken}=await login.json();
 const writes:string[]=[];
 vi.stubGlobal('fetch',(url:string,init?:RequestInit)=>{
  if(init?.method==='POST')writes.push(url);
  return real(new URL(url,base).href,init);
 });
 render(<B10Administration orderId={order!} revision={2} token={accessToken}/>);
 await screen.findByText(/tentativi automatici esauriti/);
 expect((screen.getByRole('button',{name:'Chiudi amministrativamente'}) as HTMLButtonElement).disabled).toBe(true);
 await real(`${simulator}/control/mode`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'complete'})});
 const recover=screen.getByRole('button',{name:'Verifica e riprendi richiesta'});
 await waitFor(()=>expect((recover as HTMLButtonElement).disabled).toBe(false));
 fireEvent.click(recover);
 const deadline=Date.now()+20000;
 while(!screen.queryByText(/^Confermata dal gestionale amministrativo/)){
  expect(Date.now()).toBeLessThan(deadline);
  fireEvent.click(screen.getByRole('button',{name:'Rileggi stato amministrativo'}));
  await new Promise(resolve=>setTimeout(resolve,300));
 }
 const close=screen.getByRole('button',{name:'Chiudi amministrativamente'});
 await waitFor(()=>expect((close as HTMLButtonElement).disabled).toBe(false));
 fireEvent.click(close);
 await screen.findByText(/^Chiusa amministrativamente · riferimento AMM-SIM-/);
 expect(writes).toHaveLength(2);
 expect(writes[0]).toMatch(/\/administrative-requests\/[0-9a-f-]+\/reconciliation$/);
 expect(writes[1]).toBe(`/api/v1/workshop/orders/${order}/administrative-closure`);
},40000);
