import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import MaterialNewReturn from './MaterialNewReturn';
const id='11111111-1111-4111-8111-111111111111';
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('accepted release with failed reread is unverified until explicit recovery; never resends accepted command',async()=>{
 let gets=0, posts=0;
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path==='/auth/csrf')return response({requestToken:'unit-only'});
  if(options?.method==='POST'){posts++;return response({id});}
  gets++;return gets===2?response({},503):response({pickId:id,remainingWithTechnician:gets===1?'2':'1',returned:gets===1?'0':'1',returns:[],canReturn:true,reason:"ready"});
 }));
 render(<MaterialNewReturn url='/api/v1/inventory/orders/x/lines/y/reservations/r/picks' picks={[{id,quantity:'2'}]} closed={false} blocked={false} onBlocked={()=>undefined} onApplied={async()=>undefined} onError={()=>undefined}/>);
 fireEvent.change(screen.getByLabelText('Prelievo da restituire'),{target:{value:id}});
 await screen.findByText('Residuo presso operatore: 2');
 fireEvent.change(screen.getByLabelText('Quantità da restituire'),{target:{value:'1'}});
 fireEvent.click(screen.getByRole('button',{name:'Restituisci quantità esplicita'}));
 await screen.findByText('Reso registrato; stato non verificato. Rileggi resi.');
 expect(posts).toBe(1);
 fireEvent.click(screen.getByRole('button',{name:'Rileggi resi'}));
 await screen.findByText('Stato reso riletto dal server.');
 expect(posts).toBe(1);
 expect(screen.getByText('Residuo presso operatore: 1')).toBeTruthy();
});

test.each([401,403])('controlled %s clears stale return advisory and prevents another UUID until authorized GET',async(status)=>{
 const onError=vi.fn();let posts=0;
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path==='/auth/csrf')return response({requestToken:'unit-only'});
  if(options?.method==='POST'){posts++;return response({},status);}
  return response({pickId:id,remainingWithTechnician:'1',returned:'0',returns:[],canReturn:true,reason:'ready'});
 }));
 render(<MaterialNewReturn url='/api/v1/inventory/orders/x/lines/y/reservations/r/picks' picks={[{id,quantity:'1'}]} closed={false} blocked={false} onBlocked={()=>undefined} onApplied={async()=>undefined} onError={onError}/>);
 fireEvent.change(screen.getByLabelText('Prelievo da restituire'),{target:{value:id}});
 await screen.findByText('Residuo presso operatore: 1');
 fireEvent.change(screen.getByLabelText('Quantità da restituire'),{target:{value:'0.5'}});
 fireEvent.click(screen.getByRole('button',{name:'Restituisci quantità esplicita'}));
 await screen.findByText(status===401?'Sessione terminata. Accedi nuovamente.':'Azione o scope non autorizzato. Riprova per aggiornare i permessi.');
 expect((screen.getByRole('button',{name:'Restituisci quantità esplicita'}) as HTMLButtonElement).disabled).toBe(true);
 expect(screen.queryByText('Residuo presso operatore: 1')).toBeNull();
 expect(onError).toHaveBeenCalledOnce();expect(posts).toBe(1);
 if(status===401)expect((screen.getByLabelText('Quantità da restituire') as HTMLInputElement).value).toBe('');
});

test('late authorized GET from a previous order cannot replace current return advisory',async()=>{
 let oldResolve:(v:Response)=>void=()=>undefined;
 const old=new Promise<Response>(resolve=>{oldResolve=resolve;});
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>path.includes('/old/')?old:response({pickId:id,remainingWithTechnician:'1',returned:'0',returns:[],canReturn:false,reason:'permission_or_capability'})));
 const props={picks:[{id,quantity:'1'}],closed:false,blocked:false,onBlocked:()=>undefined,onApplied:async()=>undefined,onError:()=>undefined};
 const view=render(<MaterialNewReturn url='/old/reservations/r/picks' {...props}/>);
 fireEvent.change(screen.getByLabelText('Prelievo da restituire'),{target:{value:id}});
 view.rerender(<MaterialNewReturn url='/current/reservations/r/picks' {...props}/>);
 await screen.findByText('Residuo presso operatore: 1');
 oldResolve(response({pickId:id,remainingWithTechnician:'99',returned:'0',returns:[],canReturn:true,reason:'ready'}));
 await new Promise(resolve=>setTimeout(resolve,20));
 expect(screen.queryByText('Residuo presso operatore: 99')).toBeNull();
 expect((screen.getByRole('button',{name:'Restituisci quantità esplicita'}) as HTMLButtonElement).disabled).toBe(true);
});
