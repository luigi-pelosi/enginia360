import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import ReceiptReceiving from './ReceiptReceiving';
const id='11111111-1111-4111-8111-111111111111', receiptId='22222222-2222-4222-8222-222222222222';
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
const sources=()=>({state:'ready',sources:[{id,orderedQuantity:'3.000000',unitPurchasePrice:'12.345678',externalOrderReference:'GiobbyPurchaseOrder-301',supplierName:'Fornitore',description:'Ricambio'}]});
const state=(accepted='0.000000',uncertain='0.000000',remaining='3.000000',receipts:unknown[]=[])=>({state:'ready',sourceIntentId:id,orderedQuantity:'3.000000',acceptedQuantity:accepted,uncertainQuantity:uncertain,remainingQuantity:remaining,nonAuthoritative:true,erpPerOrderResidual:null,linkKind:'internal_standalone_not_erp_native',precisionDiscrepancy:'receipt_q6_stock_report_q5_observed',receipts});
const entry=(status='PendingUnconfirmed',delivery='Uncertain',knownDocumentId:number|null=null)=>({id:receiptId,snapshot:{quantity:'2.000000',unitPrice:'12.345678'},status,externalReference:status==='Confirmed'?'GiobbyReceipt-902':null,delivery:{state:delivery,knownDocumentId,lastError:knownDocumentId?'ack_pending':'ack_unknown'}});
const mount=()=>render(<ReceiptReceiving url='/api/v1/inventory/orders/o/lines/l' warehouseId={id} onError={()=>undefined}/>);
async function choose(){await screen.findByRole('option',{name:/GiobbyPurchaseOrder-301/});fireEvent.change(screen.getByLabelText('Ordine acquisto confermato'),{target:{value:id}});await screen.findByText(/Capacità ricevimento disponibile:/);}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test('q6 quantity preview preserves a micro-unit and separates safety capacity from non-authoritative confirmed-only residual',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>response(path.includes('receipt-sources')?sources():state('0.000000','2.000000','1.000000'))));
 mount();await choose();fireEvent.change(screen.getByLabelText('Quantità da ricevere'),{target:{value:'0.000001'}});
 expect(screen.getByText('Anteprima quantità: 0.000001 · capacità dopo comando: 0.999999 (da verificare dal server)')).toBeTruthy();
 expect(screen.getByText(/Residuo interno non autorevole.*3.000000/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Quantità da ricevere'),{target:{value:'1.000001'}});expect(screen.getByText('Anteprima non valida: quantità positiva q6 entro la capacità disponibile.')).toBeTruthy();
});

test('receiving grant loss during accepted-command reread hides earlier source details while retaining the frozen command',async()=>{
 let sent=false;
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path==='/auth/csrf')return response({requestToken:'test'});
  if(options?.method==='POST'){sent=true;return response({state:'applied'},201);}
  if(sent)return response({state:'forbidden'},403);
  return response(path.includes('receipt-sources')?sources():state());
 }));
 mount();await choose();fireEvent.change(screen.getByLabelText('Quantità da ricevere'),{target:{value:'1'}});fireEvent.click(screen.getByRole('button',{name:'Crea ricevimento esplicito'}));
 await screen.findByText(/Ricevimento non autorizzato/);expect(document.body.textContent).not.toMatch(/GiobbyPurchaseOrder-301|12.345678/);
 expect((screen.getByLabelText('Quantità da ricevere') as HTMLInputElement).disabled).toBe(true);expect(screen.queryByRole('button',{name:'Riprova comando identico'})).toBeNull();
});

test('malformed delivery state fails closed without inventing a queued or confirmed receipt',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>response(path.includes('receipt-sources')?sources():state('0.000000','2.000000','1.000000',[entry('PendingUnconfirmed','Delivered',902)]))));
 mount();await screen.findByRole('option',{name:/GiobbyPurchaseOrder-301/});fireEvent.change(screen.getByLabelText('Ordine acquisto confermato'),{target:{value:id}});
 await screen.findByText('Lettura ricevimento non disponibile. Rileggi.');expect(screen.queryByText(/Capacità ricevimento disponibile/)).toBeNull();
});

test('older source read cannot overwrite a newer authoritative refresh',async()=>{
 let reads=0,resolve!:(r:Response)=>void;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{if(path.includes('receipt-sources'))return response(sources());if(++reads===1)return new Promise<Response>(r=>{resolve=r;});return response(state('0.000000','2.000000','1.000000'));}));
 mount();await screen.findByRole('option',{name:/GiobbyPurchaseOrder-301/});fireEvent.change(screen.getByLabelText('Ordine acquisto confermato'),{target:{value:id}});
 fireEvent.click(screen.getByRole('button',{name:'Rileggi ricevimenti'}));await screen.findByText('Capacità ricevimento disponibile: 1.000000');
 await act(async()=>{resolve(response(state()));});expect(screen.getByText('Capacità ricevimento disponibile: 1.000000')).toBeTruthy();
});

test.each([
 ['PendingUnconfirmed','Queued',null,'In coda · non confermato'],
 ['PendingUnconfirmed','Uncertain',null,'HOLD · ACK sconosciuto: nessun reinvio, quota impegnata'],
 ['PendingUnconfirmed','Uncertain',902,'HOLD · ACK noto: attesa di verifica esatta Giobby'],
 ['Confirmed','Completed',902,'Confermato dopo readback esatto · GiobbyReceipt-902'],
 ['PendingUnconfirmed','Completed',902,'HOLD · conferma business non ancora registrata'],
])('technical receipt %s/%s is never promoted from an ACK alone',async(status,delivery,known,text)=>{
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>response(path.includes('receipt-sources')?sources():state(status==='Confirmed'?'2.000000':'0.000000',status==='Confirmed'?'0.000000':'2.000000','1.000000',[entry(status,delivery,known as number|null)]))));
 mount();await choose();await screen.findByText(text);
 expect(screen.queryByRole('button',{name:/reinvia|nuovo UUID|rilascia|annulla|rifiuta/i})).toBeNull();
 expect(screen.queryByRole('button',{name:'Riprova comando identico'})).toBeNull();
});

test.each(['','0','-1','1.0000001','1000000','1e1',' 1','NaN','2','1.000001'])('regression invalid/excess quantity %j cannot send an API command',async(q)=>{
 const posts:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{if(options?.method==='POST')posts.push(String(options.body));return response(path.includes('receipt-sources')?sources():state('0.000000','2.000000','1.000000'));}));
 mount();await choose();fireEvent.change(screen.getByLabelText('Quantità da ricevere'),{target:{value:q}});fireEvent.click(screen.getByRole('button',{name:'Crea ricevimento esplicito'}));
 await screen.findByText(/Quantità positiva q6/);expect(posts).toHaveLength(0);expect(document.activeElement).toBe(screen.getByLabelText('Quantità da ricevere'));
});

test('regression receiving grant loss removes old price, reference and all receipt history',async()=>{
 let denied=false;
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>denied?response({state:'forbidden'},403):response(path.includes('receipt-sources')?sources():state('2.000000','0.000000','1.000000',[entry('Confirmed','Completed',902)]))));
 mount();await choose();expect(screen.getByText('Costo acquisto congelato: 12.345678')).toBeTruthy();denied=true;
 fireEvent.click(screen.getByRole('button',{name:'Rileggi ricevimenti'}));await screen.findByText(/Ricevimento non autorizzato/);
 expect(document.body.textContent).not.toMatch(/GiobbyPurchaseOrder-301|GiobbyReceipt-902|12.345678|Capacità ricevimento/);
 expect((screen.getByRole('button',{name:'Crea ricevimento esplicito'}) as HTMLButtonElement).disabled).toBe(true);
});

test('lost accepted client response freezes the original UUID and quantity until identical retry AND authoritative history reread',async()=>{
 const posts:{path:string;body:string}[]=[];let accepted=false,historyFails=true;
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  if(path==='/auth/csrf')return response({requestToken:'test'});
  if(options?.method==='POST'){posts.push({path,body:String(options.body)});accepted=true;if(posts.length===1)throw new TypeError('lost accepted response');return response({state:'replayed',id:JSON.parse(String(options.body)).id});}
  if(path.includes('receipt-sources'))return response(sources());
  if(accepted&&historyFails)return response({},503);
  return response(accepted?state('0.000000','2.000000','1.000000',[{...entry(),id:JSON.parse(posts[0].body).id}]):state());
 }));
 mount();await choose();fireEvent.change(screen.getByLabelText('Quantità da ricevere'),{target:{value:'2.000000'}});fireEvent.click(screen.getByRole('button',{name:'Crea ricevimento esplicito'}));
 await screen.findByText(/Risposta client incerta/);expect((screen.getByLabelText('Ordine acquisto confermato') as HTMLSelectElement).disabled).toBe(true);expect((screen.getByLabelText('Quantità da ricevere') as HTMLInputElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Riprova comando identico'}));await screen.findByText(/Comando registrato; rilettura autorevole ancora necessaria/);
 expect(posts).toHaveLength(2);expect(posts[1]).toEqual(posts[0]);expect(JSON.parse(posts[0].body)).toEqual({id:expect.any(String),quantity:'2.000000'});
 expect((screen.getByLabelText('Quantità da ricevere') as HTMLInputElement).disabled).toBe(true);
 historyFails=false;fireEvent.click(screen.getByRole('button',{name:'Rileggi ricevimenti'}));await screen.findByText('Capacità ricevimento disponibile: 1.000000');
 expect(screen.queryByRole('button',{name:'Riprova comando identico'})).toBeNull();expect((screen.getByLabelText('Quantità da ricevere') as HTMLInputElement).disabled).toBe(false);
});
