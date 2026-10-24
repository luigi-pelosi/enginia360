import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdministrativeWorkspace from './AdministrativeWorkspace';
import { parseEditor } from './editorContracts';
import { editorView, id, summary } from './editorFixtures';
import { actions, administrativeClosure, closureId, delivery, gate, request, requestId, state, technical } from './administrativeFixtures';
const editor = parseEditor({ ...editorView, revision: 9, summary: { ...summary, revision: 9 } }, id);
const base = '/api/v1/workshop/orders/' + id;
type Handler = (options?: RequestInit) => Response | Promise<Response>;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function server(routes: Record<string, Handler | unknown>) {
  const calls: { path: string; options?: RequestInit }[] = [];
  const fetch = vi.fn(async (path: string, options?: RequestInit) => {
    calls.push({ path, options });
    if (path === '/auth/csrf') return json({ requestToken: 'test-only' });
    const route = routes[(options?.method ?? 'GET') + ' ' + path];
    if (route === undefined) return json({}, 404);
    return typeof route === 'function' ? (route as Handler)(options) : json(route);
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, calls, posts: () => calls.filter(c => c.options?.method === 'POST') };
}
const noop = () => { };
const open = (over: Record<string, unknown> = {}) => ({ ['GET ' + base + '/closure-actions']: actions(over), ['GET ' + base + '/technical-closure-gate']: gate(), ['GET ' + base + '/closure-state']: state('Open') });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('open order: the carcass gate is a requirement only and technical closure posts the fresh server revision with a fixed command id', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(closureId as `${string}-${string}-${string}-${string}-${string}`);
  let closed = false;
  const s = server({
    ['GET ' + base + '/closure-actions']: () => json(closed ? actions({ technicalClosure: technical, canCompleteTechnical: false, canRequestAdministrative: true, actionReasons: [] }) : actions()),
    ['GET ' + base + '/technical-closure-gate']: gate(),
    ['GET ' + base + '/closure-state']: () => json(closed ? state('TechnicallyClosed') : state('Open')),
    ['POST ' + base + '/technical-closure']: () => { closed = true; return json(technical, 201); },
  });
  const onChanged = vi.fn(async () => { });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={onChanged} />);
  expect(await screen.findByText('Requisito carcassa: Clear')).toBeTruthy();
  expect(screen.getByText(/non prova che tutta la commessa sia chiudibile/)).toBeTruthy();
  fireEvent.click(await screen.findByRole('button', { name: 'Chiudi tecnicamente' }));
  await screen.findByText('Chiusa tecnicamente alla revisione 9; stato riletto dal server.');
  expect(screen.getByText('Chiusa tecnicamente alla revisione 9')).toBeTruthy();
  const [post] = s.posts();
  expect(post.path).toBe(base + '/technical-closure');
  expect(post.options?.body).toBe(JSON.stringify({ id: closureId, expectedRevision: 9 }));
  expect(onChanged).toHaveBeenCalledOnce();
  expect(screen.queryByRole('button', { name: 'Chiudi tecnicamente' })).toBeNull();
});
