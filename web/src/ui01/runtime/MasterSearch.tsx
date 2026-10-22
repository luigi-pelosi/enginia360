import { useEffect, useRef, useState } from 'react';
import { request } from './workshopApi';
import { check, positive, record, uuid } from './contracts';

export type MasterChoice = Readonly<{ id: string; label: string; kind?: 'Service' | 'Part'; version?: number }>;
type Props = Readonly<{
  endpoint?: string; label: string; value?: MasterChoice; catalog?: boolean; legalName?: boolean;
  onChange: (choice?: MasterChoice) => void; onError: (error: unknown) => void; disabledKinds?: readonly string[];
}>;
// Each context owns its instance (key=endpoint). Generations also reject overlapping searches and unmount responses.
export default function MasterSearch({ endpoint, label, value, catalog = false, legalName = false, onChange, onError, disabledKinds = [] }: Props) {
  const [draft, setDraft] = useState(''), [query, setQuery] = useState(''), [rows, setRows] = useState<MasterChoice[]>([]);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [after, setAfter] = useState('');
  const generation = useRef(0);
  const noun = label.toLocaleLowerCase('it');
  async function search(term: string, cursor = '') {
    const gen = ++generation.current;
    setRows([]); setAfter(''); setBusy(!!endpoint); onChange(undefined);
    if (!endpoint) { setMessage('Nessun contesto assegnato.'); return; }
    setMessage('Ricerca in corso…'); setQuery(term);
    try {
      const raw = await request(endpoint+'&search='+encodeURIComponent(term)+'&limit=20'+(cursor ? '&after='+cursor : ''));
      check(Array.isArray(raw) && raw.length <= 20);
      const parsed = raw.map(item => {
        const r = record(item), name = r[legalName ? 'legalName' : 'label'];
        check(uuid(r.id) && typeof name === 'string');
        if (catalog) check(['Service','Part'].includes(r.kind as string) && positive(r.version));
        return { id: r.id, label: name, ...(catalog ? { kind: r.kind, version: r.version } : {}) } as MasterChoice;
      });
      check(new Set(parsed.map(r => r.id)).size === parsed.length);
      if (gen !== generation.current) return;
      setRows(parsed); setAfter(parsed.length === 20 ? parsed[19].id : '');
      setMessage(parsed.length ? 'Risultati: '+parsed.length+'. Seleziona; nessun prezzo o stock implicito.' : 'nessun risultato.');
    } catch (error) {
      if (gen !== generation.current) return;
      setMessage((error as Error).message); onError(error);
    } finally { if (gen === generation.current) setBusy(false); }
  }
  useEffect(() => { void search(''); return () => { generation.current++; }; }, [endpoint]);
  return <div>
    <label>Ricerca {noun}<input maxLength={200} value={draft} disabled={!endpoint} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); void search(draft); } }} /></label>
    <button type="button" disabled={!endpoint} onClick={() => void search(draft)}>Cerca {noun}</button>
    <p role="status">{label}: {message}</p>
    <label>{label}<select aria-label={label} disabled={!endpoint || busy} value={value?.id ?? ''} onChange={e => onChange(rows.find(r => r.id === e.target.value))}>
      <option value="">Seleziona</option>{rows.map(r => <option key={r.id} value={r.id} disabled={!!r.kind && disabledKinds.includes(r.kind)}>{r.kind ? r.kind+' · ' : ''}{r.label}</option>)}
    </select></label>
    <button type="button" disabled={!endpoint || busy || !after} onClick={() => void search(query, after)}>Pagina successiva {noun}</button>
    <button type="button" disabled={!endpoint || busy} onClick={() => void search(query)}>Prima pagina {noun}</button>
  </div>;
}
