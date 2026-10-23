import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, decimal, positive, record } from './contracts';
import { codeMessages } from './editorMessages';
import MasterSearch, { type MasterChoice } from './MasterSearch';
import type { Editor, Row } from './editorContracts';

type Fields = Record<string, unknown>;
const discountOk = (v: string) => /^\d{1,3}(?:\.\d{1,2})?$/.test(v) && Number(v) <= 100;
const NOT_SUPPORTED = 'Non supportato in questo incremento: ';
const unsupported = ['Cambia testata', 'Cambia pagante', 'Cambia veicolo', 'Sposta riga tra lavorazioni (trascinamento)', 'Ripartizione / garanzia', 'Appuntamenti e autorizzazioni', 'Logistica ricambi (prenotazione, prelievo, installazione, carcassa)'];

// Every write is a closed server command. A transport-uncertain command is frozen and can only be replayed byte-identically.
export default function OrderWorkspace({ editor, onApplied, onError }: Readonly<{ editor: Editor; onApplied: () => Promise<void>; onError: (error: unknown) => void }>) {
  const { capabilities: caps, linePolicy: policy, order } = editor;
  const frozen = useRef<Fields | undefined>(undefined);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('Pronto.'), [uncertain, setUncertain] = useState(false);
  const [groupTitle, setGroupTitle] = useState(''), [rename, setRename] = useState<{ id: string; title: string }>();
  const [lineGroup, setLineGroup] = useState(''), [item, setItem] = useState<MasterChoice>(), [quantity, setQuantity] = useState(''), [price, setPrice] = useState(''), [discount, setDiscount] = useState('0'), [description, setDescription] = useState('');
  const [catalogMessage, setCatalogMessage] = useState('');
  const [noteGroup, setNoteGroup] = useState(''), [noteText, setNoteText] = useState('');
  const [focusId, setFocusId] = useState<string>();
  // The edit row is replaced by the stable display row: focus can only move after that render.
  useEffect(() => { if (focusId && !edit) { document.getElementById('row-' + focusId)?.focus(); setFocusId(undefined); } });
  const [edit, setEdit] = useState<{ row: Row; quantity: string; price: string; discount: string; description: string }>();
  const ready = policy.state === 'ready' && !caps.closed;
  const writeBlocked = busy || uncertain;
  const reason = caps.closed ? 'Commessa chiusa tecnicamente: sola lettura.' : policy.state !== 'ready' ? 'Policy righe non configurata: nessuna scrittura.' : '';
  const defaultGroup = (value: string) => editor.groups.some(g => g.id === value) ? value : editor.groups[0]?.id ?? '';

  async function send(type: string, fields: Fields): Promise<boolean> {
    if (busy) return false;
    const body = frozen.current ?? { type, commandId: crypto.randomUUID(), expectedRevision: editor.revision, expectedLinePolicyVersion: policy.currentLinePolicyVersion,
      expectedStructurePolicyVersion: policy.structurePolicyVersion, groupId: null, lineId: null, title: null, description: null, catalogItemId: null, catalogVersion: null,
      quantity: null, unitPrice: null, discountPercent: null, ...fields };
    frozen.current = body; setBusy(true); setMessage('Salvataggio in corso…');
    try {
      const receipt = record(await request('/api/v1/workshop/orders/' + order.id + '/editor/commands', body));
      check(receipt.commandId === body.commandId && positive(receipt.appliedRevision));
      frozen.current = undefined; setUncertain(false);
      setMessage('Scrittura accettata; rilettura del workspace…');
      try { await onApplied(); setMessage('Comando registrato alla revisione ' + receipt.appliedRevision + '; workspace riletto dal server.'); }
      catch { setMessage('Scrittura accettata; riepilogo non verificato. Rileggi commessa.'); }
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status < 500) {
        frozen.current = undefined; setUncertain(false);
        setMessage(e.code && codeMessages[e.code] ? codeMessages[e.code] : e.message);
        onError(e);
      } else { setUncertain(true); setMessage('Esito incerto: riprova solo lo stesso comando identico, oppure rileggi.'); }
      return false;
    } finally { setBusy(false); }
  }
  function invalid(id: string, text: string) { setMessage(text); document.getElementById(id)?.focus(); }
  async function addGroup() {
    if (!groupTitle.trim() || groupTitle.length > 100) return invalid('new-group-title', 'Titolo lavorazione obbligatorio (max 100 caratteri).');
    if (await send('AddGroup', { groupId: crypto.randomUUID(), title: groupTitle.trim() })) setGroupTitle('');
  }
  async function addLine() {
    const group = defaultGroup(lineGroup);
    if (!group) return invalid('line-group', 'Crea prima una lavorazione.');
    if (!item) return invalid('line-catalog', 'Seleziona articolo o prestazione.');
    if (!decimal(quantity) || !/[1-9]/.test(quantity)) return invalid('line-quantity', 'Quantità positiva, punto decimale, max 6 interi e 6 decimali.');
    if (!decimal(price)) return invalid('line-price', 'Prezzo non negativo, max 6 interi e 6 decimali.');
    if (!discountOk(discount)) return invalid('line-discount', 'Sconto da 0 a 100 con max 2 decimali.');
    if (description.length > policy.limits.maxDescriptionLength) return invalid('line-description', 'Descrizione troppo lunga.');
    if (await send('AddCommercialLine', { lineId: crypto.randomUUID(), groupId: group, catalogItemId: item.id, catalogVersion: item.version, quantity, unitPrice: price, discountPercent: discount, description: description || null })) {
      setQuantity(''); setPrice(''); setDiscount('0'); setDescription(''); setItem(undefined);
    }
  }
  async function addNote() {
    const group = defaultGroup(noteGroup);
    if (!group) return invalid('note-group', 'Crea prima una lavorazione.');
    if (!noteText.trim() || noteText.length > policy.limits.maxDescriptionLength) return invalid('note-text', 'Nota obbligatoria (max ' + policy.limits.maxDescriptionLength + ' caratteri).');
    if (await send('AddNote', { lineId: crypto.randomUUID(), groupId: group, description: noteText })) setNoteText('');
  }
  async function applyEdit() {
    if (!edit) return;
    const r = edit.row;
    if (r.kind === 'Note') {
      if (!edit.description.trim()) return invalid('edit-description', 'Nota obbligatoria.');
      if (await send('EditNote', { lineId: r.id, description: edit.description })) { setEdit(undefined); setFocusId(r.id); }
      return;
    }
    const l = r.line!;
    const fields: Fields = { lineId: r.id };
    if (r.kind === 'Service') { if (!decimal(edit.quantity) || !/[1-9]/.test(edit.quantity)) return invalid('edit-quantity', 'Quantità positiva, max 6 decimali.'); if (edit.quantity !== l.quantity) fields.quantity = edit.quantity; }
    if (!decimal(edit.price)) return invalid('edit-price', 'Prezzo non negativo, max 6 decimali.');
    if (!discountOk(edit.discount)) return invalid('edit-discount', 'Sconto da 0 a 100, max 2 decimali.');
    if (edit.price !== l.unitPrice) fields.unitPrice = edit.price;
    if (edit.discount !== l.discountPercent) fields.discountPercent = edit.discount;
    if (edit.description !== (r.description ?? '')) fields.description = edit.description;
    if (Object.keys(fields).length === 1) return invalid('edit-price', 'Nessuna differenza da registrare.');
    if (await send('EditCommercialLine', fields)) { setEdit(undefined); setFocusId(r.id); }
  }
  const startEdit = (row: Row) => setEdit({ row, quantity: row.line?.quantity ?? '', price: row.line?.unitPrice ?? '', discount: row.line?.discountPercent ?? '', description: row.description ?? '' });

  return <section className="ui01-workspace-editor" aria-label="Workspace commessa">
    <p>Documento v{policy.documentConfigurationVersion} · Policy righe {policy.currentLinePolicyVersion === null ? 'non configurata' : 'v' + policy.currentLinePolicyVersion} · Struttura v{policy.structurePolicyVersion} · Revisione {editor.revision}{caps.closed ? ' · CHIUSA' : ''}</p>
    <p role="status" aria-live="polite">{message}</p>
    {reason && <p role="alert">{reason}</p>}
    {uncertain && <button onClick={() => { const t = frozen.current?.type as string; void send(t, {}); }} disabled={busy}>Riprova comando identico</button>}
    {uncertain && <button onClick={() => { frozen.current = undefined; setUncertain(false); void onApplied(); }} disabled={busy}>Rileggi e abbandona comando</button>}
    <form onSubmit={e => { e.preventDefault(); void addGroup(); }}><fieldset disabled={!ready || !caps.canWriteGroups || writeBlocked}>
      <label>Nuova lavorazione<input id="new-group-title" value={groupTitle} maxLength={100} onChange={e => setGroupTitle(e.target.value)} /></label><button>Aggiungi lavorazione</button>
      {!policy.multipleWorkingGroups && editor.groups.length > 0 && <small>Il profilo documento ammette una sola lavorazione.</small>}
    </fieldset></form>
    <form onSubmit={e => { e.preventDefault(); void addLine(); }} onKeyDown={e => { if (e.key === 'Escape' && !busy && !uncertain) { setItem(undefined); setQuantity(''); setPrice(''); setDiscount('0'); setDescription(''); } }}>
      <fieldset disabled={!ready || !caps.canAddLine || writeBlocked}>
        <label>Lavorazione riga<select id="line-group" value={defaultGroup(lineGroup)} onChange={e => setLineGroup(e.target.value)}>{editor.groups.map(g => <option key={g.id} value={g.id}>{g.title}</option>)}</select></label>
        <MasterSearch key={order.id + order.legalEntityId + order.siteId} endpoint={'/api/v1/workshop/catalog?legalEntityId=' + order.legalEntityId + '&siteId=' + order.siteId} label="Articolo / prestazione" catalog value={item} onChange={setItem} onError={e => { setCatalogMessage('Catalogo non disponibile: il selettore richiede orders.create.'); onError(e); }} />
        {catalogMessage && <small role="status">{catalogMessage}</small>}
        <label>Quantità<input id="line-quantity" value={quantity} onChange={e => setQuantity(e.target.value)} /></label>
        <label>Prezzo unitario<input id="line-price" value={price} onChange={e => setPrice(e.target.value)} /></label>
        <label>Sconto %<input id="line-discount" value={discount} onChange={e => setDiscount(e.target.value)} /></label>
        <label>Descrizione operatore<input id="line-description" value={description} onChange={e => setDescription(e.target.value)} /></label>
        <button>Aggiungi riga</button>
      </fieldset></form>
    <form onSubmit={e => { e.preventDefault(); void addNote(); }}><fieldset disabled={!ready || !caps.canWriteNotes || writeBlocked}>
      <label>Lavorazione nota<select id="note-group" value={defaultGroup(noteGroup)} onChange={e => setNoteGroup(e.target.value)}>{editor.groups.map(g => <option key={g.id} value={g.id}>{g.title}</option>)}</select></label>
      <label>Nota (solo descrizione, non commerciale)<input id="note-text" value={noteText} onChange={e => setNoteText(e.target.value)} /></label><button>Aggiungi nota</button>
    </fieldset></form>
    {editor.groups.length === 0 && <p>Nessuna lavorazione: aggiungine una per inserire righe.</p>}
    {editor.groups.map(g => {
      const rows = editor.rows.filter(r => r.workingGroupId === g.id);
      return <section key={g.id} className="ui01-group" aria-label={'Lavorazione ' + g.title}>
        <h2>{rename?.id === g.id ? <input aria-label={'Titolo lavorazione ' + g.title} id="rename-title" value={rename.title} onChange={e => setRename({ id: g.id, title: e.target.value })}
          onKeyDown={e => { if (e.key === 'Escape') setRename(undefined); if (e.key === 'Enter') { e.preventDefault(); if (rename.title.trim()) void send('RenameGroup', { groupId: g.id, title: rename.title.trim() }).then(ok => ok && setRename(undefined)); } }} /> : g.title}</h2>
        <button disabled={!ready || !caps.canWriteGroups || writeBlocked} onClick={() => setRename({ id: g.id, title: g.title })}>Rinomina lavorazione</button>
        <button disabled={!ready || !caps.canWriteGroups || writeBlocked || rows.length > 0} title={rows.length ? 'La lavorazione contiene righe o note.' : undefined} onClick={() => void send('RemoveEmptyGroup', { groupId: g.id })}>Rimuovi lavorazione vuota</button>
        <table><thead><tr><th>Tipo</th><th>Descrizione</th><th>Quantità</th><th>Prezzo</th><th>Sconto %</th><th>Netto salvato</th><th>Azioni</th></tr></thead><tbody>
          {rows.map(r => edit?.row.id === r.id ? <tr key={r.id}><td>{r.kind}</td>
            <td><input id="edit-description" aria-label="Descrizione riga" value={edit.description} onChange={e => setEdit({ ...edit, description: e.target.value })} onKeyDown={e => { if (e.key === 'Escape') { setEdit(undefined); setFocusId(r.id); } if (e.key === 'Enter') { e.preventDefault(); void applyEdit(); } }} /></td>
            {r.kind === 'Note' ? <td colSpan={4} /> : <>
              <td>{r.kind === 'Service' ? <input id="edit-quantity" aria-label="Quantità riga" value={edit.quantity} onChange={e => setEdit({ ...edit, quantity: e.target.value })} onKeyDown={e => { if (e.key === 'Escape') { setEdit(undefined); setFocusId(r.id); } if (e.key === 'Enter') { e.preventDefault(); void applyEdit(); } }} /> : <span title={NOT_SUPPORTED + 'quantità ricambio'}>{r.line!.quantity}</span>}</td>
              <td><input id="edit-price" aria-label="Prezzo riga" value={edit.price} onChange={e => setEdit({ ...edit, price: e.target.value })} onKeyDown={e => { if (e.key === 'Escape') { setEdit(undefined); setFocusId(r.id); } if (e.key === 'Enter') { e.preventDefault(); void applyEdit(); } }} /></td>
              <td><input id="edit-discount" aria-label="Sconto riga" value={edit.discount} onChange={e => setEdit({ ...edit, discount: e.target.value })} onKeyDown={e => { if (e.key === 'Escape') { setEdit(undefined); setFocusId(r.id); } if (e.key === 'Enter') { e.preventDefault(); void applyEdit(); } }} /></td><td>{r.line!.netAmount}</td></>}
            <td><button disabled={writeBlocked} onClick={() => void applyEdit()}>Applica</button><button onClick={() => { setEdit(undefined); setFocusId(r.id); }}>Annulla</button></td></tr>
            : <tr key={r.id}><td>{r.kind === 'Note' ? 'Nota' : r.kind}</td><td>{r.kind === 'Note' ? r.description : <>{r.line!.catalogLabel}{r.description ? ' — ' + r.description : ''}<small>{r.line!.catalogItemId} v{r.line!.catalogVersion}</small></>}</td>
              <td>{r.line?.quantity ?? ''}</td><td>{r.line?.unitPrice ?? ''}</td><td>{r.line?.discountPercent ?? ''}</td><td>{r.line?.netAmount ?? ''}</td>
              <td><button id={'row-' + r.id} disabled={!ready || writeBlocked || !(r.kind === 'Note' ? caps.canWriteNotes : caps.canEditLine)} onClick={() => startEdit(r)}>Modifica</button>
                <button disabled={!ready || writeBlocked || !(r.kind === 'Note' ? caps.canWriteNotes : caps.canRemoveLine) || r.kind === 'Part'} title={r.kind === 'Part' ? NOT_SUPPORTED + 'la rimozione dei ricambi richiede la fence con Inventory.' : undefined}
                  onClick={() => void send('RemoveLine', { lineId: r.id })}>Rimuovi</button></td></tr>)}
        </tbody></table></section>;
    })}
    <details open><summary>Funzioni non disponibili</summary>
      {unsupported.map(name => <button key={name} disabled title={NOT_SUPPORTED + 'richiede un contratto e una policy separati (R03.a.2/a.3, R03.b, R04).'}>{name}</button>)}
      <p>{caps.materialStructureEditReason ?? 'Modifica strutturale dei ricambi non supportata.'}</p></details>
  </section>;
}
