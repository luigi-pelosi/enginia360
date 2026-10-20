import { useRef, useState } from 'react';

type Line = { lineNumber: number; accountCode: string; accountDescription: string; debit: string; credit: string };
type Entry = { id: string; invoiceId: string; invoiceReference: string; entryDate: string; currency: 'EUR';
  lines: Line[]; totalDebit: string; totalCredit: string; difference: string; balanced: boolean;
  invoiceLinkState: 'Pending' | 'Linked' | 'Conflict' };
type Props = { invoiceId: string; token: string; chartVersion: number; entryId?: string };
const record = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const uuid = (x: unknown): x is string => typeof x === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);
const decimal = (x: unknown): x is string => typeof x === 'string' && /^-?\d{1,16}\.\d{6}$/.test(x);
const UNCONFIRMED = 'Registrazione non confermata. Rileggi oppure riprova lo stesso tentativo.';
const LINK: Record<string, string> = {
  Pending: 'collegamento alla fattura non ancora registrato — riprova lo stesso comando',
  Linked: 'collegata alla fattura confermata',
  Conflict: 'collegamento incoerente: verifica prima di procedere',
};
function parse(x: unknown, invoiceId: string): Entry {
  if (!record(x) || !uuid(x.id) || x.invoiceId !== invoiceId || x.currency !== 'EUR'
    || ![x.totalDebit, x.totalCredit, x.difference].every(decimal)
    || typeof x.balanced !== 'boolean' || typeof x.invoiceLinkState !== 'string' || !(x.invoiceLinkState in LINK)
    || !Array.isArray(x.lines) || x.lines.length < 2
    || !x.lines.every(line => record(line) && Number.isInteger(line.lineNumber)
      && typeof line.accountCode === 'string' && /^[0-9]{4,20}$/.test(line.accountCode)
      && typeof line.accountDescription === 'string' && decimal(line.debit) && decimal(line.credit))) throw new Error();
  // A displayed entry must be balanced by its own values, never trusted from the flag alone.
  const sum = (field: 'debit' | 'credit') => (x.lines as Line[])
    .reduce((total, line) => total + Math.round(Number(line[field]) * 1e6), 0);
  if (sum('debit') !== sum('credit') || !x.balanced || Number(x.difference) !== 0) throw new Error();
  return x as Entry;
}

// B13: technical journal entry of the F04 reference case; not real bookkeeping or a fiscal filing.
export default function B13JournalEntry({invoiceId, token, chartVersion, entryId}: Props) {
  const [entry, setEntry] = useState<Entry>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const commandId = useRef(crypto.randomUUID());
  const auth = {'Authorization': ['Bearer', token].join(' '), 'Content-Type': 'application/json'};
  async function request(path: string, body?: unknown) {
    let response: Response;
    try {
      response = await fetch(`/api/v1/accounting/invoice-journal-entries${path}`,
        {method: body ? 'POST' : 'GET', headers: auth, ...(body ? {body: JSON.stringify(body)} : {})});
    } catch { throw new Error(UNCONFIRMED); }
    if (!response.ok) throw new Error(response.status === 409
      ? 'Registrazione incompatibile con lo stato corrente: la fattura confermata resta invariata. Rileggi.' : UNCONFIRMED);
    try { return parse(await response.json(), invoiceId); } catch { throw new Error(UNCONFIRMED); }
  }
  async function run(action: () => Promise<Entry>) {
    if (busy) return; setBusy(true); setError('');
    try { setEntry(await action()); } catch (failure) { setError(failure instanceof Error ? failure.message : UNCONFIRMED); }
    finally { setBusy(false); }
  }
  return <section aria-label="Registrazione contabile tecnica">
    <h3>Registrazione contabile tecnica</h3>
    <p>Scrittura tecnica del caso di riferimento, derivata dalla fattura interna confermata. Non è contabilità reale, invio fiscale o incasso.</p>
    <button disabled={busy} onClick={() => void run(() => request('',
      {id: commandId.current, invoiceId, chartVersion}))}>Registra scrittura</button>
    <button disabled={busy || (entry === undefined && entryId === undefined)}
      onClick={() => void run(() => request(`/${entry?.id ?? entryId}`))}>Rileggi registrazione</button>
    {entry && <div aria-live="polite">
      <p>Scrittura quadrata · Dare {entry.totalDebit} = Avere {entry.totalCredit} {entry.currency} · differenza {entry.difference}</p>
      <p>Fattura {entry.invoiceReference} · {LINK[entry.invoiceLinkState]}</p>
      <table><tbody>
        {entry.lines.map(line => <tr key={line.lineNumber}>
          <td>{line.accountCode}</td><td>{line.accountDescription}</td>
          <td>Dare {line.debit}</td><td>Avere {line.credit}</td></tr>)}
      </tbody></table>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
