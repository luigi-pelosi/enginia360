import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { request, ApiError } from './workshopApi';
import CreateOrder from './CreateOrder';
import OrderWorkspace from './OrderWorkspace';
import MaterialOperations from './MaterialOperations';
import OwnActualTime from './OwnActualTime';
const AdministrativeWorkspace = lazy(() => import('./AdministrativeWorkspace'));
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
  const [timeOpen, setTimeOpen] = useState(false);
  const [closureOpen, setClosureOpen] = useState(false);
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
  return <main className="ui01-workspace"><header className="ui01-topbar"><strong>Enginia360 · Editor runtime</strong><a href="/">Accesso e amministrazione</a></header>
    <div className="ui01-runtime-session"><span role="status">{status}</span><Button size="small" disabled={busy} onClick={() => void session()}>Riprova sessione</Button>{!authenticated && csrf && <form method="post" action="/auth/login"><input type="hidden" name="__RequestVerificationToken" value={csrf} /><button>Accedi</button></form>}</div>
    <form onSubmit={e => { e.preventDefault(); void load(locator); }}><label>UUID commessa<input value={locator} onChange={e => setLocator(e.target.value)} /></label><button disabled={busy || !authenticated}>Rileggi commessa</button></form>
    <div className="ui01-body"><aside className="ui01-context">{authenticated && <OwnContexts onError={optionalFailed} />}{authenticated && <OrderList onOpen={id => { setLocator(id); void load(id); }} onError={optionalFailed} />}{order ? <details open><summary>Testata salvata · sola lettura</summary><p>Società: {order.legalEntityId}</p><p>Sede: {order.siteId}</p><p>Tipo documento: {order.documentTypeId}</p><p>Configurazione documento: {order.configurationVersion}</p><p>Ordine cliente: {order.isCustomerOrder ? 'Sì' : 'No'}</p><p>Pagante: {order.payerId}</p><p>Veicolo: {order.vehicleId}</p><p>Intestatario: {order.vehicleHolderId}</p></details> : authenticated && !busy && !locator && <CreateOrder onCreated={async id => { setLocator(id); window.location.hash = 'order='+id; await load(id, true); }} onError={failed} />}</aside><section className="ui01-document">
    <h1>{order ? 'Commessa '+order.id : 'Nessuna commessa caricata'}</h1>
    <div className="ui01-operations">{['Prenotazione','Prelievo','Preparazione','Installazione / consumo','Carcassa','Esito amministrativo esterno'].map(name => <div key={name}><span>{name}</span><strong>{name === 'Esito amministrativo esterno' ? 'Disponibile nel pannello Chiusura e attesa amministrativa' : 'Disponibile nel pannello Materiali'}</strong></div>)}</div>
    {authenticated && editor && <OrderWorkspace key={editor.order.id} editor={editor} onApplied={async () => { await load(editor.order.id, true); }} onError={optionalFailed} />}
    {authenticated && editor && <div className="ui01-panels"><details open={materialsOpen} onToggle={e => setMaterialsOpen(e.currentTarget.open)}><summary>Operazioni materiali</summary>{materialsOpen && <MaterialOperations key={'materials:'+editor.order.id} editor={editor} onError={optionalFailed} />}</details>
    <details open={timeOpen} onToggle={e => setTimeOpen(e.currentTarget.open)}><summary>Tempo effettivo mio</summary>{timeOpen && <OwnActualTime key={'time:'+editor.order.id} editor={editor} onError={optionalFailed} />}</details>
    <details open={closureOpen} onToggle={e => setClosureOpen(e.currentTarget.open)}><summary>Chiusura e attesa amministrativa</summary>{closureOpen && <Suspense fallback={<p role="status">Caricamento pannello…</p>}><AdministrativeWorkspace key={'closure:'+editor.order.id} editor={editor} onError={optionalFailed} onChanged={() => load(editor.order.id, true)} /></Suspense>}</details></div>}
    {authenticated && order && <MasterAuthority key={'authority:'+order.legalEntityId} companyId={order.legalEntityId} counterpartyId={order.payerId} onError={optionalFailed} />}
    </section></div><footer className="ui01-summary">{summary ? <><span>Imponibile {summary.netAmount}</span><span>IVA {summary.taxAmount}</span><strong>{summary.total} EUR</strong></> : 'Riepilogo non verificato'}</footer></main>;
}
