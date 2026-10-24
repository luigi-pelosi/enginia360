import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import OwnActualTime from './OwnActualTime';
import { parseEditor } from './editorContracts';
import { editorView, id } from './editorFixtures';
const group = '33333333-3333-4333-8333-333333333333', entry = '44444444-4444-4444-8444-444444444444';
const editor = parseEditor({ ...editorView, groups: [{ id: group, title: 'Tempo', version: 1, sequence: 1 }] }, id);
const item = { entryId: entry, workingGroupId: group, version: 1, workDate: '2026-01-01', durationSeconds: 100, note: 'Nota personale riservata', recordedAt: '2026-10-24T00:00:00Z' };
const page = (revision = 1) => ({ orderId: id, ownRevision: revision, closed: false, canRecord: true, entries: [item], nextAfter: null });
const history = { orderId: id, entryId: entry, workingGroupId: group, versions: [{ ...item, correctionNote: null, internalIdentityId: id, membershipId: id, commandId: id, ownRevision: 1 }], nextAfterVersion: null };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test('401 clears saved own rows, private history, correction draft and actions before notifying session owner', async () => {
    let revoked = false;
    const onError = vi.fn();
    vi.stubGlobal('fetch', vi.fn(async (path: string) => new Response(JSON.stringify(revoked ? {} : path.includes('/history') ? history : page()), { status: revoked ? 401 : 200 })));
    render(<OwnActualTime editor={editor} onError={onError}/>);
    await screen.findByText(item.note);
    fireEvent.click(screen.getByRole('button', { name: 'Storico mio' }));
    await screen.findByRole('region', { name: 'Storico tempo mio' });
    fireEvent.click(screen.getByRole('button', { name: 'Correggi tempo mio' }));
    fireEvent.change(screen.getByLabelText('Motivo correzione'), { target: { value: 'Motivo personale' } });
    revoked = true;
    fireEvent.click(screen.getByRole('button', { name: 'Rileggi tempi miei' }));
    await waitFor(() => expect(onError).toHaveBeenCalledOnce());
    expect(screen.queryByRole('region', { name: 'Storico tempo mio' })).toBeNull();
    expect(screen.queryByText(item.note)).toBeNull();
    expect(screen.queryByLabelText('Motivo correzione')).toBeNull();
    expect((screen.getByLabelText('Nota tempo') as HTMLInputElement).value).toBe('');
});
test('authoritative own revision change invalidates old correction draft instead of rebasing to fresh revision', async () => {
    let revision = 1;
    const fetch = vi.fn(async () => new Response(JSON.stringify(page(revision))));
    vi.stubGlobal('fetch', fetch);
    render(<OwnActualTime editor={editor} onError={() => { }}/>);
    await screen.findByText(item.note);
    fireEvent.click(screen.getByRole('button', { name: 'Correggi tempo mio' }));
    fireEvent.change(screen.getByLabelText('Durata effettiva (secondi)'), { target: { value: '999' } });
    revision = 2;
    fireEvent.click(screen.getByRole('button', { name: 'Rileggi tempi miei' }));
    await screen.findByText(/Revisione propria 2/);
    expect(screen.queryByRole('button', { name: 'Salva correzione tempo' })).toBeNull();
    expect((screen.getByLabelText('Durata effettiva (secondi)') as HTMLInputElement).value).toBe('');
    expect(fetch.mock.calls).toHaveLength(2);
});
test('accepted receipt followed by failed reread clears unverifiable current state and blocks another write until explicit reread', async () => {
    let accepted = false;
    vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
        if (path === '/auth/csrf')
            return new Response('{"requestToken":"synthetic"}');
        if (options?.method === 'POST') {
            const b = JSON.parse(options.body as string);
            accepted = true;
            return new Response(JSON.stringify({ commandId: b.commandId, entryId: b.entryId, orderId: id, appliedOwnRevision: 2, entryVersion: 1, resultKind: 'Created' }));
        }
        return new Response(JSON.stringify(accepted ? {} : page()), { status: accepted ? 503 : 200 });
    }));
    render(<OwnActualTime editor={editor} onError={() => { }}/>);
    await screen.findByText(item.note);
    fireEvent.change(screen.getByLabelText('Lavorazione tempo'), { target: { value: group } });
    fireEvent.change(screen.getByLabelText('Data lavoro'), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText('Durata effettiva (secondi)'), { target: { value: '125' } });
    fireEvent.click(screen.getByRole('button', { name: 'Registra tempo' }));
    await screen.findByText('Registrato; rilettura non verificata.');
    expect(screen.queryByText(item.note)).toBeNull();
    expect((screen.getByRole('button', { name: 'Registra tempo' }).closest('fieldset') as HTMLFieldSetElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: 'Riprova tempo identico' })).toBeNull();
});
test('unchanged correction is a focused no-op, not a new command or receipt', async () => {
    const fetch = vi.fn(async (path: string, options?: RequestInit) => new Response(JSON.stringify(path === '/auth/csrf' ? { requestToken: 'synthetic' } : options?.method === 'POST' ? { code: 'actual_time_no_change' } : page()), { status: options?.method === 'POST' ? 409 : 200 }));
    vi.stubGlobal('fetch', fetch);
    render(<OwnActualTime editor={editor} onError={() => { }}/>);
    await screen.findByText(item.note);
    fireEvent.click(screen.getByRole('button', { name: 'Correggi tempo mio' }));
    fireEvent.click(screen.getByRole('button', { name: 'Salva correzione tempo' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Nessuna differenza da registrare.');
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
    expect(document.activeElement).toBe(screen.getByLabelText('Durata effettiva (secondi)'));
});
test('invalid duration is associated with an announced error and focused without a command', async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify(page())));
    vi.stubGlobal('fetch', fetch);
    render(<OwnActualTime editor={editor} onError={() => { }}/>);
    await screen.findByText(item.note);
    fireEvent.change(screen.getByLabelText('Lavorazione tempo'), { target: { value: group } });
    fireEvent.change(screen.getByLabelText('Data lavoro'), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText('Durata effettiva (secondi)'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Registra tempo' }));
    const input = screen.getByLabelText('Durata effettiva (secondi)');
    expect(document.activeElement).toBe(input);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe('time-field-error');
    expect(document.getElementById('time-field-error')?.getAttribute('role')).toBe('alert');
    expect(fetch).toHaveBeenCalledOnce();
});
test('Escape discards only the correction draft and restores keyboard focus to its saved entry', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(page()))));
    render(<OwnActualTime editor={editor} onError={() => { }}/>);
    await screen.findByText(item.note);
    const edit = screen.getByRole('button', { name: 'Correggi tempo mio' });
    fireEvent.click(edit);
    fireEvent.change(screen.getByLabelText('Durata effettiva (secondi)'), { target: { value: '999' } });
    fireEvent.keyDown(screen.getByLabelText('Durata effettiva (secondi)'), { key: 'Escape' });
    expect(screen.queryByRole('button', { name: 'Salva correzione tempo' })).toBeNull();
    expect(screen.getByText(item.note)).toBeTruthy();
    expect(document.activeElement).toBe(edit);
});
test('own entry pagination uses only the server UUID cursor and does not prefetch unbounded records', async () => {
    const fetch = vi.fn(async (path: string) => new Response(JSON.stringify(path.includes('after=') ? { ...page(), entries: [], nextAfter: null } : { ...page(), nextAfter: entry })));
    vi.stubGlobal('fetch', fetch);
    render(<OwnActualTime editor={editor} onError={() => { }}/>);
    await screen.findByText(item.note);
    const more = screen.queryByRole('button', { name: 'Altri tempi miei' });
    expect(more).not.toBeNull();
    fireEvent.click(more!);
    await waitFor(() => expect(fetch.mock.calls[1][0]).toBe('/api/v1/workshop/orders/' + id + '/actual-time/own?limit=20&after=' + entry));
    await waitFor(() => expect(screen.queryByText(item.note)).toBeNull());
    expect(fetch).toHaveBeenCalledTimes(2);
});
