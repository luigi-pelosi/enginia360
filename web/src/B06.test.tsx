import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import B06Reservations from './B06Reservations';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test('recovered committed command does not suppress a new equal-sized explicit partial', async () => {
  const warehouse = '11111111-1111-1111-1111-111111100101';
  const ids: string[] = [];
  let committed = 0;
  let failRead = false;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/warehouses?')) return Response.json([{id: warehouse, name: 'Magazzino sintetico'}]);
    if (init?.method === 'POST') {
      const command = JSON.parse(init.body as string) as {id: string};
      if (!ids.includes(command.id)) committed++;
      ids.push(command.id);
      if (committed === 1) failRead = true;
      return Response.json({id: command.id}, {status: 201});
    }
    if (failRead) { failRead = false; return new Response('{}', {status:503}); }
    return Response.json({physical:'2', available:String(2-committed*.5), reserved:String(committed*.5), remaining:String(3-committed*.5),
      reservations:ids.map(id=>({id}))});
  }));
  render(<B06Reservations order={{id:'order',legalEntityId:'company',siteId:'site'}} line={{id:'line',catalogVersion:1}} token="synthetic"/>);
  await screen.findByRole('option', {name:'Magazzino sintetico'});
  fireEvent.change(screen.getByLabelText('Magazzino prenotazione'), {target:{value:warehouse}});
  await screen.findByText('Disponibile: 2');
  fireEvent.change(screen.getByLabelText('Quantità da prenotare'), {target:{value:'.5'}});
  // Strict invariant lexical form, no leading-dot shorthand.
  fireEvent.click(screen.getByRole('button', {name:'Prenota quantità esplicita'}));
  await screen.findByText(/Inserisci una quantità positiva/);
  expect(ids).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('Quantità da prenotare'), {target:{value:'0.5'}});
  fireEvent.click(screen.getByRole('button', {name:'Prenota quantità esplicita'}));
  await screen.findByText(/Stato non disponibile/);
  fireEvent.click(screen.getByRole('button', {name:'Rileggi prenotazioni'}));
  await screen.findByText('Prenotato sulla riga: 0.5');
  fireEvent.click(screen.getByRole('button', {name:'Prenota quantità esplicita'}));
  await screen.findByText('Prenotato sulla riga: 1');
  expect(ids).toHaveLength(2);
  expect(ids[0]).not.toBe(ids[1]);
});
