import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, record } from './contracts';
import type { Editor } from './editorContracts';
import { parseOwnTime, parseOwnHistory, type OwnTime, type OwnEntry, type OwnHistory } from './actualTimeContracts';
export default function OwnActualTime({ editor, onError }: Readonly<{
    editor: Editor;
    onError: (e: unknown) => void;
}>) {
    const id = editor.order.id, path = '/api/v1/workshop/orders/' + id + '/actual-time/own';
    const [saved, setSaved] = useState<OwnTime>(), [message, setMessage] = useState('Lettura…'), [busy, setBusy] = useState(false);
    const [group, setGroup] = useState(''), [date, setDate] = useState(''), [seconds, setSeconds] = useState(''), [note, setNote] = useState('');
    const [edit, setEdit] = useState<OwnEntry>(), [reason, setReason] = useState(''), [history, setHistory] = useState<OwnHistory>();
    const gen = useRef(0), pending = useRef(false);
    const frozen = useRef<Readonly<{
        url: string;
        body: string;
        commandId: string;
        entryId: string;
        revision: number;
        version: number;
        kind: string;
    }> | undefined>(undefined);
    const [uncertain, setUncertain] = useState(false);
    const [fieldError, setFieldError] = useState<{
        id: string;
        text: string;
    }>();
    function error(e: unknown) { setMessage(e instanceof Error ? e.message : 'Servizio non disponibile.'); if (e instanceof ApiError && e.status === 401) {
        gen.current++;
        frozen.current = undefined;
        setUncertain(false);
        setSaved(undefined);
        setHistory(undefined);
        setEdit(undefined);
        setReason('');
        setGroup('');
        setDate('');
        setSeconds('');
        setNote('');
    } onError(e); }
    async function load(after?: string) { const g = ++gen.current; try {
        const data = parseOwnTime(await request(path + (after ? '?limit=20&after=' + after : '')), id);
        if (g === gen.current) {
            if (saved && (saved.ownRevision !== data.ownRevision || !data.canRecord)) {
                setEdit(undefined);
                setDate('');
                setSeconds('');
                setNote('');
                setReason('');
                setHistory(undefined);
                setMessage('Tempi cambiati: bozza scartata, riparti dai valori riletti.');
            }
            setSaved(data);
        }
    }
    catch (e) {
        if (g === gen.current)
            error(e);
        throw e;
    } }
    useEffect(() => { void load().catch(() => { }); return () => { gen.current++; }; }, [id]);
    function invalid(field: string, text: string) { setMessage(text); setFieldError({ id: field, text }); document.getElementById(field)?.focus(); }
    const field = (id: string) => ({ 'aria-invalid': fieldError?.id === id || undefined, 'aria-describedby': fieldError?.id === id ? 'time-field-error' : undefined });
    async function save() {
        if (pending.current || uncertain || !saved)
            return;
        const target = editor.groups.find(g => g.id === group);
        if (!edit && !target)
            return invalid('time-group', 'Seleziona lavorazione.');
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date))
            return invalid('time-date', 'Data ISO richiesta.');
        if (!/^\d+$/.test(seconds) || Number(seconds) < 1 || Number(seconds) > 2147483647)
            return invalid('time-duration', 'Durata intera positiva in secondi richiesta.');
        if (note.length > 500 || /[\u0000-\u001f\u007f-\u009f]/.test(note))
            return invalid('time-note', 'Nota senza controlli, massimo 500 caratteri.');
        if (edit && date === edit.workDate && Number(seconds) === edit.durationSeconds && note === edit.note)
            return invalid('time-duration', 'Nessuna differenza da registrare.');
        const commandId = crypto.randomUUID(), entryId = edit?.entryId ?? crypto.randomUUID();
        const command = edit ? { commandId, expectedOwnRevision: saved.ownRevision, expectedEntryVersion: edit.version, workDate: date, durationSeconds: Number(seconds), note, correctionNote: reason } : { commandId, entryId, workingGroupId: group, expectedOwnRevision: saved.ownRevision, expectedGroupVersion: target!.version, workDate: date, durationSeconds: Number(seconds), note };
        frozen.current = Object.freeze({ url: edit ? path + '/' + entryId + '/corrections' : path, body: JSON.stringify(command), commandId, entryId, revision: saved.ownRevision + 1, version: edit ? edit.version + 1 : 1, kind: edit ? 'Corrected' : 'Created' });
        await sendFrozen();
    }
    async function sendFrozen() {
        const command = frozen.current;
        if (!command || pending.current)
            return;
        pending.current = true;
        setBusy(true);
        const g = gen.current;
        try {
            const csrf = record(await request('/auth/csrf'));
            check(typeof csrf.requestToken === 'string');
            if (g !== gen.current)
                return;
            const response = await fetch(command.url, { method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf.requestToken as string }, body: command.body });
            if (!response.ok) {
                const failure = await response.json().catch(() => null);
                throw new ApiError(response.status, failure?.code ?? failure?.error);
            }
            const receipt = record(await response.json());
            check(receipt.orderId === id && receipt.commandId === command.commandId && receipt.entryId === command.entryId && receipt.appliedOwnRevision === command.revision && receipt.entryVersion === command.version && receipt.resultKind === command.kind);
            if (g !== gen.current)
                return;
            frozen.current = undefined;
            setUncertain(false);
            setDate('');
            setSeconds('');
            setNote('');
            setEdit(undefined);
            setHistory(undefined);
            setReason('');
            try {
                await load();
                setMessage('Registrato; tempi propri riletti dal server.');
            }
            catch (e) {
                setSaved(undefined);
                setHistory(undefined);
                if (!(e instanceof ApiError && e.status === 401))
                    setMessage('Registrato; rilettura non verificata.');
            }
        }
        catch (e) {
            if (g !== gen.current)
                return;
            if (e instanceof ApiError && e.status < 500) {
                frozen.current = undefined;
                setUncertain(false);
                error(e);
            }
            else {
                setUncertain(true);
                setMessage('Esito incerto: riprova solo il comando tempo identico.');
            }
        }
        finally {
            pending.current = false;
            setBusy(false);
        }
    }
    async function readHistory(entry: string, after?: number) { const g = gen.current; try {
        const h = parseOwnHistory(await request(path + '/' + entry + '/history?limit=20' + (after ? '&afterVersion=' + after : '')), id, entry);
        if (g === gen.current)
            setHistory(h);
    }
    catch (e) {
        if (g === gen.current)
            error(e);
    } }
    function startEdit(e: OwnEntry) { setEdit(e); setGroup(e.workingGroupId); setDate(e.workDate); setSeconds(String(e.durationSeconds)); setNote(e.note); setReason(''); document.getElementById('time-date')?.focus(); }
    function cancelDraft() { if (busy || uncertain)
        return; const entry = edit?.entryId; setEdit(undefined); setDate(''); setSeconds(''); setNote(''); setReason(''); setFieldError(undefined); if (entry)
        document.getElementById('time-edit-' + entry)?.focus(); }
    return <section aria-label="Consuntivo personale"><h2>Consuntivo personale</h2><p>Tempo effettivo proprio distinto dalle ore fatturate. Nessun effetto su importi o stock.</p><p>Revisione propria {saved?.ownRevision ?? 'non verificata'} · Revisione commerciale {editor.revision}</p><p role="status">{message}</p><button disabled={busy || uncertain} onClick={() => void load().catch(() => { })}>Rileggi tempi miei</button>{uncertain && <button disabled={busy} onClick={() => void sendFrozen()}>Riprova tempo identico</button>}{saved?.closed && <p>Scritture post-chiusura non supportate in questo profilo; storico proprio disponibile.</p>}
 {fieldError && <p role="alert" id="time-field-error">{fieldError.text}</p>}<form onInput={() => setFieldError(undefined)} onKeyDown={e => { if (e.key === 'Escape') {
        e.preventDefault();
        cancelDraft();
    } }} onSubmit={e => { e.preventDefault(); void save(); }}><fieldset disabled={busy || !saved?.canRecord}><label>Lavorazione tempo<select id="time-group" {...field('time-group')} disabled={!!edit} value={group} onChange={e => setGroup(e.target.value)}><option value="">Seleziona lavorazione</option>{editor.groups.map(g => <option key={g.id} value={g.id}>{g.title}</option>)}</select></label><label>Data lavoro<input id="time-date" {...field('time-date')} type="date" value={date} onChange={e => setDate(e.target.value)}/></label><label>Durata effettiva (secondi)<input id="time-duration" {...field('time-duration')} inputMode="numeric" value={seconds} onChange={e => setSeconds(e.target.value)}/></label><label>Nota tempo<input id="time-note" {...field('time-note')} value={note} onChange={e => setNote(e.target.value)}/></label>{edit && <label>Motivo correzione<input value={reason} onChange={e => setReason(e.target.value)}/></label>}<button>{edit ? 'Salva correzione tempo' : 'Registra tempo'}</button>{edit && <button type="button" onClick={cancelDraft}>Annulla correzione</button>}</fieldset></form>
 <ul>{saved?.entries.map(e => <li key={e.entryId}>{e.workDate} · {e.durationSeconds} secondi · v{e.version}<p>{e.note}</p><button disabled={busy} onClick={() => void readHistory(e.entryId)}>Storico mio</button><button id={'time-edit-' + e.entryId} disabled={busy || !saved.canRecord} onClick={() => startEdit(e)}>Correggi tempo mio</button></li>)}</ul>{saved?.nextAfter && <button disabled={busy || uncertain} onClick={() => void load(saved.nextAfter!).catch(() => { })}>Altri tempi miei</button>}{history && <section aria-label="Storico tempo mio"><h3>Storico tempo mio</h3>{history.versions.map(v => <article key={v.version}><p>Versione {v.version} · {v.workDate} · {v.durationSeconds} secondi</p><p>{v.note}</p><p>{v.correctionNote}</p><small>Identità {v.internalIdentityId} · membership {v.membershipId} · {v.recordedAt} · comando {v.commandId}</small></article>)}{history.nextAfterVersion && <button onClick={() => void readHistory(history.entryId, history.nextAfterVersion!)}>Altre versioni mie</button>}</section>}</section>;
}
