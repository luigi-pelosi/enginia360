import { afterEach, expect, test, vi } from 'vitest';
import { request } from './workshopApi';
afterEach(() => vi.unstubAllGlobals());
test('same origin no-store read has no tenant or bearer authority', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{"authenticated":true}')); vi.stubGlobal('fetch', fetch);
  expect(await request('/auth/session')).toEqual({ authenticated: true });
  expect(fetch).toHaveBeenCalledWith('/auth/session', expect.objectContaining({ credentials: 'same-origin', cache: 'no-store' }));
  expect(fetch.mock.calls[0][1].headers).toBeUndefined();
});
test('writes obtain fresh CSRF and preserve exact invariant payload; empty conflicts are controlled', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response('{"requestToken":"fresh"}')).mockResolvedValueOnce(new Response(null, { status: 409 }));
  vi.stubGlobal('fetch', fetch);
  await expect(request('/api/v1/workshop/orders', { id: 'command', quantity: '1.123456' })).rejects.toMatchObject({ status: 409 });
  expect(fetch.mock.calls[0][0]).toBe('/auth/csrf');
  expect(fetch.mock.calls[1][1]).toMatchObject({ method: 'POST', headers: { 'X-CSRF-TOKEN': 'fresh', 'Content-Type': 'application/json' }, body: '{"id":"command","quantity":"1.123456"}' });
});
test('malformed CSRF projection refuses POST instead of sending undefined authority', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{}')); vi.stubGlobal('fetch', fetch);
  await expect(request('/api/v1/workshop/orders', { id: 'command' })).rejects.toThrow(/Contratto/);
  expect(fetch).toHaveBeenCalledTimes(1);
});
test('bounded common edit uses PUT with fresh CSRF and preserves server refusal state', async () => {
  const fetch=vi.fn().mockResolvedValueOnce(new Response('{"requestToken":"fresh"}')).mockResolvedValueOnce(new Response('{"state":"external"}',{status:409}));
  vi.stubGlobal('fetch',fetch);
  await expect(request('/api/v1/counterparties/id',{commandId:'same'},'PUT')).rejects.toMatchObject({status:409,code:'external'});
  expect(fetch.mock.calls[1][1]).toMatchObject({method:'PUT',headers:{'X-CSRF-TOKEN':'fresh'}});
});
test.each([400,401,403,404,409,503])('HTTP%s with empty body is a typed recoverable error', async status => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status })));
  await expect(request('/api/v1/workshop/contexts')).rejects.toMatchObject({ status });
});
