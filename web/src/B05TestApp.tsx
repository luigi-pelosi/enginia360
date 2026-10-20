import { useEffect, useRef, useState } from "react";
import B04TestApp from "./B04TestApp";
import B06Reservations from "./B06Reservations";
import B10Administration from "./B10Administration";
import B12Invoice from "./B12Invoice";
type Item = { id: string; kind: "Service" | "Part"; label: string; version: number };
type Line = { id: string; catalogVersion: number; catalogItemId: string; catalogLabel: string; kind: string; quantity: string; unitPrice: string; discountPercent: string; netAmount: string; workingGroupId: string; payerId: string };
type Summary = { orderId: string; payerId: string; revision: number; lines: Line[]; netAmount: string; taxAmount: string; total: string; currency: "EUR"; policy: "Case001" };
const uuid=(x:unknown):x is string=>typeof x==="string" && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);
const record=(x:unknown):x is Record<string,unknown>=>typeof x==="object" && x!==null;
const decimal=(x:unknown):x is string=>typeof x==="string" && /^\d{1,16}(\.\d{1,6})?$/.test(x);
function summary(x:unknown, orderId:string):Summary {
  if(!record(x) || x.orderId!==orderId || !uuid(x.payerId) || !Number.isInteger(x.revision) || Number(x.revision)<0 || Number(x.revision)>2 || x.currency!=="EUR" || x.policy!=="Case001" || ![x.netAmount,x.taxAmount,x.total].every(decimal)
    || !Array.isArray(x.lines) || x.lines.length!==x.revision || !x.lines.every(l=>record(l) && uuid(l.id) && uuid(l.catalogItemId) && typeof l.catalogLabel==="string" && l.catalogLabel.length<=100 && ["Service","Part"].includes(l.kind as string) && l.workingGroupId===orderId && l.payerId===x.payerId && [l.quantity,l.unitPrice,l.discountPercent,l.netAmount].every(decimal))) throw new Error("Invalid summary");
  return x as Summary;
}
export default function B05TestApp() {
  return <B04TestApp commercial={(order,token)=><CommercialLines key={order.id} order={order} token={token}/>}/>;
}
function CommercialLines({order,token}:{order:{id:string;legalEntityId:string;siteId:string};token:string}) {
  const [items,setItems]=useState<Item[]>([]);
  const [partId,setPartId]=useState('');
  const [saved,setSaved]=useState<Summary>();
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(true);
  const [valuesByKind, setValuesByKind] = useState({
    Service: {quantity: '1.50', unitPrice: '55.00', discountPercent: '10'},
    Part: {quantity: '1', unitPrice: '95.00', discountPercent: '5'}
  });
  const pending=useRef<{key:string;id:string}|undefined>(undefined);
  const alive=useRef(true);
  async function api(path:string,payload?:unknown):Promise<unknown> {
    const response=await fetch('/api/v1/workshop'+path,{method:payload===undefined?'GET':'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},...(payload===undefined?{}:{body:JSON.stringify(payload)})});
    if(!response.ok) throw new Error();
    return response.json();
  }
  async function read() { return summary(await api('/orders/'+order.id+'/commercial-summary'),order.id); }
  async function readCatalog():Promise<Item[]> {
    const rows=await api('/catalog?legalEntityId='+order.legalEntityId+'&siteId='+order.siteId);
    if(!Array.isArray(rows) || !rows.every(x=>record(x) && uuid(x.id) && ['Service','Part'].includes(x.kind as string) && typeof x.label==='string' && x.label.length<=100 && Number.isInteger(x.version) && Number(x.version)>0)) throw new Error();
    return rows as Item[];
  }
  useEffect(()=>{
    alive.current=true;
    void (async()=>{try {
      const rows=await readCatalog();
      const stored=await read();
      if(alive.current){setItems(rows as Item[]);setSaved(stored);}
    }catch{if(alive.current)setError('Valori non disponibili. Rileggi oppure riseleziona il contesto.');}
    finally{if(alive.current)setBusy(false);}})();
    return ()=>{alive.current=false;};
  },[order.id,token]);
  async function add(kind:'Service'|'Part') {
    const item=items.find(x=>x.kind===kind && (kind==='Service' || !partId || x.id===partId));
    if(busy)return;
    if(!item || !saved){setError('Catalogo o valori non disponibili. Rileggi oppure riseleziona il contesto.');return;}
    const values={catalogItemId:item.id,catalogVersion:item.version,configurationVersion:1,expectedRevision:saved.revision,
      ...valuesByKind[kind]};
    const key=JSON.stringify(values);
    if(pending.current?.key!==key)pending.current={key,id:crypto.randomUUID()};
    setBusy(true);setError('');
    try{await api('/orders/'+order.id+'/lines',{...values,id:pending.current.id});const stored=await read();if(alive.current){setSaved(stored);pending.current=undefined;}}
    catch{if(alive.current)setError('Riga non confermata. Riprova lo stesso tentativo; per conflitto o riferimenti cambiati, rileggi o riseleziona il contesto.');}
    finally{if(alive.current)setBusy(false);}
  }
  async function reload(){
    setBusy(true);setError('');setItems([]);
    try{
      const rows=await readCatalog();
      const stored=await read();
      if(alive.current){setItems(rows);setSaved(stored);}
    }catch{if(alive.current)setError('Catalogo o valori non disponibili. Rileggi oppure riseleziona un contesto autorizzato.');}
    finally{if(alive.current)setBusy(false);}
  }
  return <section aria-label="Righe commerciali">
    <h2>Valori commerciali · caso 001</h2>
    <p>Valori espliciti modificabili: quantità e prezzo fino a 6 decimali, sconto fino a 2 decimali da 0 a 100%. Netto riga e imposta aggregata 22% arrotondati HALF_UP a 6 decimali. Nessun listino, stock o fattura reale.</p>
    {(['Service', 'Part'] as const).map(kind => {
      const name = kind === 'Service' ? 'prestazione' : 'ricambio';
      return <fieldset key={kind} disabled={busy || saved?.lines.some(line => line.kind === kind)}>
        <legend>{name}</legend>
        {kind === 'Part' && <label>Articolo ricambio<select value={partId} onChange={event => setPartId(event.target.value)}>
          <option value="">Primo articolo disponibile</option>
          {items.filter(x => x.kind === 'Part').map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>}
        {([['quantity', 'Quantità'], ['unitPrice', 'Prezzo unitario'], ['discountPercent', 'Sconto %']] as const).map(([field, label]) =>
          <label key={field}>{label} {name}<input inputMode="decimal" value={valuesByKind[kind][field]}
            onChange={event => setValuesByKind(current => ({...current, [kind]: {...current[kind], [field]: event.target.value}}))}/></label>)}
      </fieldset>;
    })}
    <p>Stessa lavorazione: {order.id}. Configurazione societaria righe: versione 1.</p>
    {items.map(x=><p key={x.id}>{x.label} · catalogo tenant, versione {x.version}</p>)}
    <button disabled={busy || items.length===0 || !saved || saved.lines.some(x=>x.kind==='Service')} onClick={()=>void add('Service')}>Aggiungi prestazione</button>
    <button disabled={busy || items.length===0 || !saved || saved.lines.some(x=>x.kind==='Part')} onClick={()=>void add('Part')}>Aggiungi ricambio</button>
    <button disabled={busy} onClick={()=>void reload()}>Rileggi valori salvati</button>
    {saved && <div aria-live="polite">
      {saved.lines.map(x=><p key={x.id}>{x.catalogLabel} · {x.quantity} × {x.unitPrice} EUR · sconto {x.discountPercent}% · netto {x.netAmount} EUR</p>)}
      {import.meta.env.VITE_B06_TEST_UI === 'true' && saved.lines.filter(x => x.kind === 'Part').map(line =>
        <B06Reservations key={line.id} order={order} line={line} token={token}/>)}
      <p>Soggetto unico a carico: {saved.payerId}</p>
      <p>Imponibile: {saved.netAmount} EUR</p><p>Imposta aggregata: {saved.taxAmount} EUR</p><p>Totale: {saved.total} EUR</p>
      {(import.meta.env.VITE_B10_TEST_UI === 'true' || import.meta.env.VITE_B12_TEST_UI === 'true') && <B10Administration orderId={order.id} revision={saved.revision} token={token}/>}
      {import.meta.env.VITE_B12_TEST_UI === 'true' && <B12Invoice orderId={order.id} token={token}
        documentTypeId="11111111-7777-0000-0000-000000000010" configurationVersion={1} documentDate={new Date().toISOString().slice(0,10)}/>}
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
