import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, record, uuid } from './contracts';
type Entry = { revision: number; unitPurchasePrice: string };
type PriceState = { entry: Entry | null; history: Entry[]; revision: number; canManage: boolean; requiresManualPrice: boolean; provisionalUnitPurchasePrice: string | null; supplier: { id: string; name: string; revision: number }; item: { id: string; label: string; version: number }; authorityVersion: number | null };
const q6=/^[0-9]{1,6}(\.[0-9]{1,6})?$/;
function parse(value: unknown): PriceState {
 const r=record(value);check(r.state==='ready' && typeof r.canManage==='boolean' && typeof r.requiresManualPrice==='boolean' && Number.isInteger(r.revision) && Array.isArray(r.history));
 const supplier=record(r.supplier),item=record(r.item);
 check(uuid(supplier.id) && typeof supplier.name==='string' && Number.isInteger(supplier.revision) && uuid(item.id) && typeof item.label==='string' && Number.isInteger(item.version));
 for(const entry of r.history as unknown[]) {const h=record(entry);check(Number.isInteger(h.revision) && typeof h.unitPurchasePrice==='string' && q6.test(h.unitPurchasePrice));}
 check(r.entry===null || (record(r.entry).revision===r.revision && typeof record(r.entry).unitPurchasePrice==='string' && q6.test(record(r.entry).unitPurchasePrice as string)));
 check(r.requiresManualPrice===(r.entry===null) && r.provisionalUnitPurchasePrice===(r.entry===null?'0.000000':null));
 return r as unknown as PriceState;
}
export default function SupplierPurchasePrices({ companyId, onError, onBlocked }: Readonly<{ companyId: string; onError?: (e: unknown)=>void; onBlocked?: (blocked:boolean)=>void }>) {
 const [supplier,setSupplier]=useState(''),[item,setItem]=useState(''),[price,setPrice]=useState('');
 const [state,setState]=useState<PriceState>(),[message,setMessage]=useState('Seleziona fornitore e articolo; rileggi il listino.'),[busy,setBusy]=useState(false);
 const generation=useRef(0);
 const pending=useRef<{path:string;body:string}|undefined>(undefined);
 const [uncertain,setUncertain]=useState(false);
 const [readback,setReadback]=useState(false);
 useEffect(()=>{onBlocked?.(busy||uncertain||readback);},[busy,uncertain,readback,onBlocked]);
 useEffect(()=>()=>onBlocked?.(false),[onBlocked]);
 useEffect(()=>()=>{generation.current++;},[]);
 const path='/api/v1/catalog/suppliers/'+supplier+'/items/'+item+'/purchase-price';
 function change(set:(value:string)=>void,value:string) {generation.current++;set(value);setState(undefined);setPrice('');}
 async function read(saved=readback) {
  if(!uuid(supplier)||!uuid(item)){setMessage('Inserisci UUID validi di fornitore e articolo.');return;}
  const gen=++generation.current;setBusy(true);setState(undefined);
  try {const value=parse(await request(path+'?legalEntityId='+companyId));if(gen!==generation.current)return;setState(value);setReadback(false);setPrice(value.entry?.unitPurchasePrice??'');setMessage(saved?'Prezzo salvato e riletto — revisione '+value.revision:'Listino riletto dal server.');}
  catch(e){if(gen===generation.current){if(saved)setReadback(true);setMessage(saved?'Prezzo accettato; rilettura non verificata. Rileggi il listino.':'Lettura listino non disponibile.');onError?.(e);}}
  finally{if(gen===generation.current)setBusy(false);}
 }
 async function save() {
  if(busy||!state?.canManage)return;
  if(!pending.current){
   if(!q6.test(price)){setMessage('Inserisci il prezzo esplicito con massimo 6 decimali; zero deliberato ammesso.');return;}
   pending.current={path,body:JSON.stringify({legalEntityId:companyId,commandId:crypto.randomUUID(),expectedRevision:state.revision,supplierRevision:state.supplier.revision,catalogVersion:state.item.version,authorityVersion:state.authorityVersion,unitPurchasePrice:price})};
  }
  const command=pending.current;
  const gen=generation.current;setBusy(true);
  try {
   const receipt=record(await request(command.path,JSON.parse(command.body),'PUT')),body=JSON.parse(command.body);
   check((receipt.state==='applied'||receipt.state==='replayed') && receipt.commandId===body.commandId && receipt.revision===body.expectedRevision+1);
   if(gen===generation.current){pending.current=undefined;setUncertain(false);setReadback(true);await read(true);}
  }catch(e){if(gen===generation.current){
   if(e instanceof ApiError && e.status<500){pending.current=undefined;setUncertain(false);setState(undefined);setMessage(e.message);onError?.(e);}
   else{setUncertain(true);setMessage('Esito prezzo incerto: riprova solo il comando identico.');}
  }}
  finally{if(gen===generation.current)setBusy(false);}
 }
 return <section aria-label="Listini acquisto fornitori"><p>Listino della società {companyId}</p><p role="status">{message}</p>
  <label>UUID fornitore listino<input disabled={busy||uncertain||readback} value={supplier} onChange={e=>change(setSupplier,e.target.value)}/></label>
  <label>UUID articolo listino<input disabled={busy||uncertain||readback} value={item} onChange={e=>change(setItem,e.target.value)}/></label>
  <button disabled={busy||uncertain} onClick={()=>void read()}>Rileggi listino</button>
  {uncertain && <button disabled={busy} onClick={()=>void save()}>Riprova prezzo identico</button>}
  {state && <><p>{state.supplier.name} · {state.item.label}</p><p>{state.entry?'Prezzo presente: '+state.entry.unitPurchasePrice:'Prezzo assente: 0.000000 provvisorio — inserimento manuale obbligatorio prima dell’invio.'}</p>
   <label>Prezzo unitario acquisto<input disabled={busy||uncertain||!state.canManage} value={price} onChange={e=>setPrice(e.target.value)}/></label>
   {state.canManage && <button disabled={busy||uncertain} onClick={()=>void save()}>Salva prezzo acquisto</button>}
   {state.history.map(h=><p key={h.revision}>Revisione {h.revision} · {h.unitPurchasePrice}</p>)}
  </>}
 </section>;
}
