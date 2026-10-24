import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import MaterialRelease from './MaterialRelease';
const id='11111111-1111-4111-8111-111111111111';
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('accepted release with failed reread is unverified until explicit recovery; never resends accepted command',async()=>{
 let gets=0, posts=0;
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path==='/auth/csrf')return response({requestToken:'unit-only'});
  if(options?.method==='POST'){posts++;return response({id});}
  gets++;return gets===2?response({},503):response({reservationId:id,remainingReleasable:gets===1?'2':'1',released:gets===1?'0':'1',releases:[],canRelease:true});
 }));
 render(<MaterialRelease url='/api/v1/inventory/orders/x/lines/y' reservations={[{id,quantity:'2'}]} closed={false} blocked={false} onBlocked={()=>undefined} onApplied={async()=>undefined} onError={()=>undefined}/>);
 fireEvent.change(screen.getByLabelText('Prenotazione da rilasciare'),{target:{value:id}});
 await screen.findByText('Residuo mai prelevato rilasciabile: 2');
 fireEvent.change(screen.getByLabelText('Quantità da rilasciare'),{target:{value:'1'}});
 fireEvent.click(screen.getByRole('button',{name:'Rilascia quantità esplicita'}));
 await screen.findByText('Rilascio registrato; stato non verificato. Rileggi rilasci.');
 expect(posts).toBe(1);
 fireEvent.click(screen.getByRole('button',{name:'Rileggi rilasci'}));
 await screen.findByText('Stato rilascio riletto dal server.');
 expect(posts).toBe(1);
 expect(screen.getByText('Residuo mai prelevato rilasciabile: 1')).toBeTruthy();
});
