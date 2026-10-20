import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import B08Installation from './B08Installation';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test('rereading a consumed installation after response loss refreshes displayed stock', async () => {
  const changed = vi.fn();
  let reads = 0;
  vi.stubGlobal('fetch', (_url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return Promise.reject(new Error('Lost committed response'));
    reads++;
    const entry = { installation: { id: '11111111-1111-1111-1111-111111111111', quantity: '1' }, stockEffect: 'Consumed',
      consumption: { installationId: '11111111-1111-1111-1111-111111111111', quantity: '1' } };
    return Promise.resolve(new Response(JSON.stringify({picked:'2',installed:reads===1?'0':'1',remainingToInstall:reads===1?'2':'1',installations:reads===1?[]:[entry]}),{status:200}));
  });
  render(<B08Installation url="/installation-test" token="synthetic" onChanged={changed}/>);
  const button = screen.getByRole('button',{name:'Installa quantità esplicita'});
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('Quantità da installare'),{target:{value:'1'}});
  fireEvent.click(button);
  await screen.findByText(/Installazione non confermata/);
  fireEvent.click(screen.getByRole('button',{name:'Rileggi installazioni'}));
  await screen.findByText('Installato: 1');
  expect(changed).toHaveBeenCalledOnce();
});
