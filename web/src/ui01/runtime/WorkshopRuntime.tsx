import { useEffect, useRef, useState } from 'react';
import { request, ApiError } from './workshopApi';
import CreateOrder from './CreateOrder';
import AddLine from './AddLine';
import OwnContexts from './OwnContexts';
import MasterAuthority from './MasterAuthority';
import { Button } from 'antd';
import { parseOrder, parseSummary, uuid, type Order, type Summary } from './contracts';
export default function WorkshopRuntime() {
  const [order, setOrder] = useState<Order>(); const [summary, setSummary] = useState<Summary>();
  const [locator, setLocator] = useState(new URLSearchParams(window.location.hash.slice(1)).get('order') ?? '');
  const [status, setStatus] = useState('Verifica sessione…'); const [busy, setBusy] = useState(false);
  const [authenticated, setAuthenticated] = useState(false), [csrf, setCsrf] = useState('');
  const generation = useRef(0);
  function failed(e: unknown) {
    setStatus(e instanceof Error ? e.message : 'Servizio non disponibile.');
    if (e instanceof ApiError && e.status === 401) { generation.current++; setAuthenticated(false); setCsrf(''); setOrder(undefined); setSummary(undefined); setBusy(false); }
  }
  function optionalFailed(e: unknown) {
    // Independent selector/panel errors remain visible in that panel, not in the saved-read state.
    if (e instanceof ApiError && e.status === 401) failed(e);
  }
  async function session() {
    const gen = ++generation.current; setAuthenticated(false); setOrder(undefined); setSummary(undefined); setCsrf(''); setStatus('Verifica sessione…');
    try { const s = await request('/auth/session') as { authenticated: boolean }; const token = await request('/auth/csrf') as { requestToken: string }; if (gen !== generation.current) return; setCsrf(token.requestToken); if (!s.authenticated) { setStatus('Sessione terminata. Accedi nuovamente.'); return; } setAuthenticated(true); if (locator) await load(locator); else setStatus('Sessione attiva. Apri un UUID noto o crea una commessa.'); } catch(e) { if (gen === generation.current) failed(e); }
  }
  async function load(id: string, accepted = false) {
    const gen = ++generation.current; setBusy(true); setStatus('Lettura…'); setOrder(undefined); setSummary(undefined);
    try {
      if (!uuid(id)) throw new Error('Inserisci UUID commessa valido.');
      const o = parseOrder(await request('/api/v1/workshop/orders/'+id), id);
      const s = parseSummary(await request('/api/v1/workshop/orders/'+id+'/commercial-summary'), o);
      if (gen !== generation.current) return;
      setOrder(o); setSummary(s); setStatus('Valori salvati riletti — revisione '+s.revision); window.location.hash = 'order='+id;
    } catch (e) { if (gen === generation.current) { failed(e); if (accepted && !(e instanceof ApiError && e.status === 401)) setStatus('Scrittura accettata; riepilogo non verificato. Rileggi commessa. '+(e as Error).message); } }
    finally { if (gen === generation.current) setBusy(false); }
  }
  useEffect(() => { void session(); return () => { generation.current++; }; }, []);
  return <main className="ui01-workspace"><header className="ui01-topbar"><strong>Enginia360 · Editor runtime</strong><a href="/">Accesso e amministrazione</a></header>
    <div className="ui01-runtime-session"><span role="status">{status}</span><Button size="small" disabled={busy} onClick={() => void session()}>Riprova sessione</Button>{!authenticated && csrf && <form method="post" action="/auth/login"><input type="hidden" name="__RequestVerificationToken" value={csrf} /><button>Accedi</button></form>}</div>
    <form onSubmit={e => { e.preventDefault(); void load(locator); }}><label>UUID commessa<input value={locator} onChange={e => setLocator(e.target.value)} /></label><button disabled={busy || !authenticated}>Rileggi commessa</button></form>
    <div className="ui01-body"><aside className="ui01-context">{authenticated && <OwnContexts onError={optionalFailed} />}{order ? <details open><summary>Testata salvata · sola lettura</summary><p>Società: {order.legalEntityId}</p><p>Sede: {order.siteId}</p><p>Tipo documento: {order.documentTypeId}</p><p>Configurazione documento: {order.configurationVersion}</p><p>Ordine cliente: {order.isCustomerOrder ? 'Sì' : 'No'}</p><p>Pagante: {order.payerId}</p><p>Veicolo: {order.vehicleId}</p><p>Intestatario: {order.vehicleHolderId}</p></details> : authenticated && !busy && !locator && <CreateOrder onCreated={async id => { setLocator(id); window.location.hash = 'order='+id; await load(id, true); }} onError={failed} />}</aside><section className="ui01-document">
    <h1>{order ? 'Commessa '+order.id : 'Nessuna commessa caricata'}</h1>
    <div className="ui01-operations">{['Prenotazione','Prelievo','Preparazione','Installazione / consumo','Carcassa','Esito amministrativo esterno'].map(name => <div key={name}><span>{name}</span><strong>Non collegato in UI01.b</strong><button disabled aria-label={'Gestisci '+name}>Non disponibile</button></div>)}</div>
    <p>R03: modifica/rimozione righe, Note, multigruppo e cambio testata non disponibili. Nessuna modifica locale è persistita.</p>
    {['Modifica righe','Rimuovi righe','Note','Nuova lavorazione','Cambia pagante','Cambia veicolo','Elenco commesse'].map(name => <button key={name} disabled>{name}</button>)}
    {summary && <section className="ui01-group"><h2>Lavorazione {summary.orderId}</h2><table><thead><tr><th>Tipo</th><th>Descrizione</th><th>Quantità</th><th>Prezzo</th><th>Sconto %</th><th>Netto salvato</th></tr></thead><tbody>{summary.lines.map(l => <tr key={l.id}><td>{l.kind}</td><td>{l.catalogLabel}<small>{l.id}</small></td><td>{l.quantity}</td><td>{l.unitPrice}</td><td>{l.discountPercent}</td><td>{l.netAmount}</td></tr>)}</tbody></table></section>}
    {authenticated && order && summary && !busy && <AddLine key={order.id} order={order} summary={summary} onSaved={async () => { await load(order.id, true); }} onError={optionalFailed} />}
    {authenticated && order && <MasterAuthority key={'authority:'+order.legalEntityId} companyId={order.legalEntityId} counterpartyId={order.payerId} onError={optionalFailed} />}
    </section></div><footer className="ui01-summary">{summary ? <><span>Imponibile {summary.netAmount}</span><span>IVA {summary.taxAmount}</span><strong>{summary.total} EUR</strong></> : 'Riepilogo non verificato'}</footer></main>;
}
