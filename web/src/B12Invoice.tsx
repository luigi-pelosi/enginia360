import { useRef, useState } from 'react';

type Line = { id: string; catalogLabel: string; quantity: string; netAmount: string };
type Summary = { orderId: string; revision: number; lines: Line[]; netAmount: string; taxAmount: string; total: string; currency: 'EUR' };
type Party = { legalName: string };
type Invoice = { id: string; orderId: string; reference: string; status: 'Draft' | 'Confirmed'; summary: Summary;
  issuer: Party | null; recipient: Party | null; confirmedAt: string | null };
type Props = { orderId: string; token: string; documentTypeId: string; configurationVersion: number; documentDate: string };
const record = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const uuid = (x: unknown): x is string => typeof x === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);
const UNCONFIRMED = 'Operazione non confermata. Rileggi oppure riprova lo stesso tentativo.';
const decimal = (x: unknown): x is string => typeof x === 'string' && /^\d{1,16}(\.\d{1,6})?$/.test(x);
const party = (x: unknown): x is Party => record(x) && typeof x.legalName === 'string' && x.legalName.length > 0 && x.legalName.length <= 200;
function parse(x: unknown, orderId: string): Invoice {
  if (!record(x) || !uuid(x.id) || x.orderId !== orderId || !['Draft','Confirmed'].includes(x.status as string)
    || typeof x.reference !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9/.-]{0,63}$/.test(x.reference)
    || !record(x.summary) || x.summary.orderId !== orderId || x.summary.currency !== 'EUR'
    || ![x.summary.netAmount,x.summary.taxAmount,x.summary.total].every(decimal)
    || !Array.isArray(x.summary.lines) || !x.summary.lines.every(line => record(line) && uuid(line.id)
      && typeof line.catalogLabel === 'string' && line.catalogLabel.length <= 100 && decimal(line.quantity) && decimal(line.netAmount))
    || (x.status === 'Confirmed' && (!party(x.issuer) || !party(x.recipient) || typeof x.confirmedAt !== 'string'))
    || (x.status === 'Draft' && (x.issuer !== null || x.recipient !== null || x.confirmedAt !== null))) throw new Error();
  return x as Invoice;
}
export default function B12Invoice({orderId, token, documentTypeId, configurationVersion, documentDate}: Props) {
  const [invoice, setInvoice] = useState<Invoice>();
  const [reference, setReference] = useState('FV-001/2026');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const invoiceId = useRef(crypto.randomUUID());
  const confirmationId = useRef(crypto.randomUUID());
  const auth = {'Authorization': ['Bearer', token].join(' '), 'Content-Type': 'application/json'};
  async function request(path: string, body?: unknown) {
    let response: Response;
    try { response = await fetch(`/api/v1/billing/workshop-invoices${path}`, {method: body ? 'POST' : 'GET', headers: auth,
      ...(body ? {body: JSON.stringify(body)} : {})}); } catch { throw new Error(UNCONFIRMED); }
    if (!response.ok) throw new Error(response.status === 409 ? 'Operazione incompatibile con lo stato corrente. Rileggi.' : UNCONFIRMED);
    try { return parse(await response.json(), orderId); } catch { throw new Error(UNCONFIRMED); }
  }
  async function run(action: () => Promise<Invoice>) {
    if (busy) return; setBusy(true); setError('');
    try { setInvoice(await action()); } catch (failure) { setError(failure instanceof Error ? failure.message : UNCONFIRMED); }
    finally { setBusy(false); }
  }
  return <section aria-label="Fattura tecnica interna">
    <h3>Fattura tecnica interna</h3>
    <p>Documento interno derivato dalla chiusura tecnica. Non è emissione fiscale e non invia dati a sistemi esterni.</p>
    <label>Riferimento <input value={reference} maxLength={64} onChange={event => setReference(event.target.value)}/></label>
    <button disabled={busy || invoice !== undefined} onClick={() => void run(() => request('', {id: invoiceId.current, orderId,
      documentTypeId, configurationVersion, documentDate, currency: 'EUR', reference}))}>Crea bozza tecnica</button>
    <button disabled={busy || invoice?.status !== 'Draft'} onClick={() => void run(() => request(`/${invoice!.id}/confirmation`,
      {id: confirmationId.current, configurationVersion}))}>Conferma documento interno</button>
    <button disabled={busy || invoice === undefined} onClick={() => void run(() => request(`/${invoice!.id}`))}>Rileggi documento</button>
    {invoice && <div aria-live="polite">
      <p>{invoice.status === 'Draft' ? 'Bozza tecnica creata' : 'Documento interno confermato'}</p>
      <p>Riferimento {invoice.reference} · Totale {invoice.summary.total} {invoice.summary.currency}</p>
      <ul>{invoice.summary.lines.map(line => <li key={line.id}>{line.catalogLabel}: {line.quantity} · {line.netAmount} EUR</li>)}</ul>
      {invoice.status === 'Confirmed' && <p>Emittente {invoice.issuer?.legalName} · Destinatario {invoice.recipient?.legalName}</p>}
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
