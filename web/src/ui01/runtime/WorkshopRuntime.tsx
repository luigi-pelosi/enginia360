import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { request, ApiError } from './workshopApi';
import CreateOrder from './CreateOrder';
import OrderWorkspace from './OrderWorkspace';
import MaterialOperations from './MaterialOperations';
import OwnActualTime from './OwnActualTime';
const AdministrativeWorkspace = lazy(() => import('./AdministrativeWorkspace'));
const SupplierPurchasePrices = lazy(() => import('./SupplierPurchasePrices'));
import OrderList from './OrderList';
import OwnContexts from './OwnContexts';
import MasterAuthority from './MasterAuthority';
import { Button } from 'antd';
import { uuid, type Order } from './contracts';
import { parseEditor, type Editor } from './editorContracts';
export default function WorkshopRuntime() {
  const [editor, setEditor] = useState<Editor>(); const order: Order | undefined = editor?.order; const summary = editor?.summary;
  const [locator, setLocator] = useState(new URLSearchParams(window.location.hash.slice(1)).get('order') ?? '');
  const [status, setStatus] = useState('Verifica sessione…'); const [busy, setBusy] = useState(false);
  const [authenticated, setAuthenticated] = useState(false), [csrf, setCsrf] = useState('');
  const generation = useRef(0);
  const [materialsOpen, setMaterialsOpen] = useState(false);
  const [materialBlocked, setMaterialContextBlocked] = useState(false);
  const [priceBlocked, setPriceBlocked] = useState(false);
  const materialContextBlocked = materialBlocked || priceBlocked;
  const [timeOpen, setTimeOpen] = useState(false);
  const [closureOpen, setClosureOpen] = useState(false);
  const [pricesOpen, setPricesOpen] = useState(false);
  function failed(e: unknown) {
    setStatus(e instanceof Error ? e.message : 'Servizio non disponibile.');
    if (e instanceof ApiError && e.status === 401) { generation.current++; setAuthenticated(false); setCsrf(''); setEditor(undefined); setBusy(false); }
  }
  function optionalFailed(e: unknown) {
    // Independent selector/panel errors remain visible in that panel, not in the saved-read state.
    if (e instanceof ApiError && e.status === 401) failed(e);
  }
  async function session() {
    const gen = ++generation.current; setAuthenticated(false); setEditor(undefined); setCsrf(''); setStatus('Verifica sessione…');
    try { const s = await request('/auth/session') as { authenticated: boolean }; const token = await request('/auth/csrf') as { requestToken: string }; if (gen !== generation.current) return; setCsrf(token.requestToken); if (!s.authenticated) { setStatus('Sessione terminata. Accedi nuovamente.'); return; } setAuthenticated(true); if (locator) await load(locator); else setStatus('Sessione attiva. Apri un UUID noto o crea una commessa.'); } catch(e) { if (gen === generation.current) failed(e); }
  }
  async function load(id: string, accepted = false) {
    const gen = ++generation.current; setBusy(true); setStatus('Lettura…'); if (!accepted) setEditor(undefined);
    try {
      if (!uuid(id)) throw new Error('Inserisci UUID commessa valido.');
      const e = parseEditor(await request('/api/v1/workshop/orders/'+id+'/editor'), id);
      if (gen !== generation.current) return;
      setEditor(e); setStatus('Valori salvati riletti — revisione '+e.revision); window.location.hash = 'order='+id;
    } catch (e) { if (gen === generation.current) { failed(e); if (accepted && !(e instanceof ApiError && e.status === 401)) { setEditor(undefined); setStatus('Scrittura accettata; riepilogo non verificato. Rileggi commessa. '+(e as Error).message); } } }
    finally { if (gen === generation.current) setBusy(false); }
  }
  useEffect(() => { void session(); return () => { generation.current++; }; }, []);
  return <main className="ui01-workspace"><header className="ui01-topbar"><strong>Enginia360 · Editor runtime</strong><a href="/" aria-disabled={materialContextBlocked} onClick={e => { if (materialContextBlocked) e.preventDefault(); }}>Accesso e amministrazione</a></header>
    <div className="ui01-runtime-session"><span role="status">{status}</span>{materialContextBlocked && <span role="status">Operazione materiali in corso o incerta: risolvi il comando prima di cambiare commessa.</span>}<Button size="small" disabled={busy || materialContextBlocked} onClick={() => void session()}>Riprova sessione</Button>{!authenticated && csrf && <form method="post" action="/auth/login"><input type="hidden" name="__RequestVerificationToken" value={csrf} /><button>Accedi</button></form>}</div>
    <form onSubmit={e => { e.preventDefault(); void load(locator); }}><label>UUID commessa<input disabled={materialContextBlocked} value={locator} onChange={e => setLocator(e.target.value)} /></label><button disabled={busy || materialContextBlocked || !authenticated}>Rileggi commessa</button></form>
    <div className="ui01-body"><aside className="ui01-context"><fieldset className="ui01-context-freeze" disabled={materialContextBlocked}>{authenticated && <OwnContexts onError={optionalFailed} />}{authenticated && <OrderList onOpen={id => { setLocator(id); void load(id); }} onError={optionalFailed} />}{order ? <details open><summary>Testata salvata · sola lettura</summary><p>Società: {order.legalEntityId}</p><p>Sede: {order.siteId}</p><p>Tipo documento: {order.documentTypeId}</p><p>Configurazione documento: {order.configurationVersion}</p><p>Ordine cliente: {order.isCustomerOrder ? 'Sì' : 'No'}</p><p>Pagante: {order.payerId}</p><p>Veicolo: {order.vehicleId}</p><p>Intestatario: {order.vehicleHolderId}</p></details> : authenticated && !busy && !locator && <CreateOrder onCreated={async id => { setLocator(id); window.location.hash = 'order='+id; await load(id, true); }} onError={failed} />}</fieldset></aside><section className="ui01-document">
    <h1>{order ? 'Commessa '+order.id : 'Nessuna commessa caricata'}</h1>
    <div className="ui01-operations">{['Prenotazione','Prelievo','Preparazione','Installazione / consumo','Carcassa','Esito amministrativo esterno'].map(name => <div key={name}><span>{name}</span><strong>{name === 'Esito amministrativo esterno' ? 'Disponibile nel pannello Chiusura e attesa amministrativa' : 'Disponibile nel pannello Materiali'}</strong></div>)}</div>
    {authenticated && editor && <fieldset className="ui01-context-freeze" disabled={materialContextBlocked}><OrderWorkspace key={editor.order.id} editor={editor} onApplied={async () => { await load(editor.order.id, true); }} onError={optionalFailed} /></fieldset>}
    {authenticated && editor && <div className="ui01-panels"><details open={materialsOpen} onToggle={e => { if (materialContextBlocked && !e.currentTarget.open) e.currentTarget.open = true; else setMaterialsOpen(e.currentTarget.open); }}><summary aria-disabled={materialContextBlocked} onClick={e => { if (materialContextBlocked) e.preventDefault(); }}>Operazioni materiali</summary>{materialsOpen && <MaterialOperations key={'materials:'+editor.order.id} editor={editor} onError={optionalFailed} onContextBlocked={setMaterialContextBlocked} />}</details>
    <details open={timeOpen} onToggle={e => setTimeOpen(e.currentTarget.open)}><summary>Tempo effettivo mio</summary>{timeOpen && <OwnActualTime key={'time:'+editor.order.id} editor={editor} onError={optionalFailed} />}</details>
    <details open={closureOpen} onToggle={e => setClosureOpen(e.currentTarget.open)}><summary>Chiusura e attesa amministrativa</summary>{closureOpen && <Suspense fallback={<p role="status">Caricamento pannello…</p>}><AdministrativeWorkspace key={'closure:'+editor.order.id} editor={editor} onError={optionalFailed} onChanged={() => load(editor.order.id, true)} /></Suspense>}</details></div>}
    {authenticated && order && <MasterAuthority key={'authority:'+order.legalEntityId} companyId={order.legalEntityId} counterpartyId={order.payerId} onError={optionalFailed} />}
    {authenticated && order && <details open={pricesOpen} onToggle={e=>{if(priceBlocked&&!e.currentTarget.open)e.currentTarget.open=true;else setPricesOpen(e.currentTarget.open);}}><summary onClick={e=>{if(priceBlocked)e.preventDefault();}} aria-disabled={priceBlocked}>Listini acquisto fornitori</summary>{pricesOpen && <Suspense fallback={<p role="status">Caricamento listini…</p>}><SupplierPurchasePrices key={'prices:'+order.legalEntityId} companyId={order.legalEntityId} onError={optionalFailed} onBlocked={setPriceBlocked}/></Suspense>}</details>}
    </section></div><footer className="ui01-summary">{summary ? <><span>Imponibile {summary.netAmount}</span><span>IVA {summary.taxAmount}</span><strong>{summary.total} EUR</strong></> : 'Riepilogo non verificato'}</footer></main>;
}
