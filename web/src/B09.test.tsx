import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import B09CarcassReturn from './B09CarcassReturn';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const id = '11111111-1111-1111-1111-111111111111';
test('lost committed return is reread and the same command ID is never widened', async () => {
  const posts: Record<string, unknown>[] = [];
  let returned = false;
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') { posts.push(JSON.parse(init.body as string)); returned = true; return Promise.reject(new Error('lost')); }
    if (url.includes('technical-closure-gate')) return Promise.resolve(new Response(JSON.stringify({orderId:id,status:returned?'Clear':'Blocked',
      requirements:[{lineId:id,catalogItemId:id,requiredInstalled:'2',returned:returned?'2':'0',outstanding:returned?'0':'2'}]}),{status:200}));
    const saved = {id:posts[0]?.id ?? id,orderId:id,workingGroupId:id,lineId:id,warehouseId:id,catalogItemId:id,location:'Carcasse A',
      locationConfigurationVersion:1,description:'Carcassa',quantity:'2',installations:[],receivedAt:'2026-10-20T00:00:00Z',operatorId:id};
    return Promise.resolve(new Response(JSON.stringify({orderId:id,lineId:id,warehouseId:id,requiredInstalled:'2',returned:returned?'2':'0',
      outstanding:returned?'0':'2',returns:returned?[saved]:[]}),{status:200}));
  });
  render(<B09CarcassReturn url={`/api/v1/inventory/orders/${id}/lines/${id}`} orderId={id} warehouse={id} token="synthetic" refresh={0}/>);
  const button = await screen.findByRole('button',{name:'Registra rientro carcassa'});
  await screen.findByText('Chiusura tecnica bloccata: carcassa da rientrare 2');
  fireEvent.change(screen.getByLabelText('Descrizione carcassa'),{target:{value:'Carcassa'}});
  fireEvent.change(screen.getByLabelText('Quantità carcassa'),{target:{value:'2'}});
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  await screen.findByText(/Rientro non confermato/);
  fireEvent.click(screen.getByRole('button',{name:'Rileggi rientro carcassa'}));
  await screen.findByText('Rientrato: 2');
  await screen.findByText('Chiusura tecnica: requisito carcassa soddisfatto');
  expect(posts).toHaveLength(1);
  expect(posts[0]).toEqual({id:posts[0].id,warehouseId:id,quantity:'2',description:'Carcassa'});
});
