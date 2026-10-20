import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
const base = import.meta.env.VITE_B08_HTTP_BASE as string | undefined;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules(); });
test.skipIf(!base)("B08 real DOM/HTTP explicit installation and lost-response retry", async () => {
  const realFetch = globalThis.fetch;
  const writes: Record<string, unknown>[] = [];
  let failRead = false;
  let failPickRead = true;
  let losePickResponse = true;
  const fault = import.meta.env.VITE_B08_STOCK_FAULT === 'true';
  let loseInstallationResponse = !fault;
  const installationWrites: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
    if (url.endsWith('/installations') && init?.method === 'POST') {
      installationWrites.push(JSON.parse(init.body as string));
      return realFetch(new URL(url, base).href, init).then(response => {
        if (response.ok && loseInstallationResponse) { loseInstallationResponse = false; throw new Error('Injected lost committed installation response'); }
        return response;
      });
    }
    if (url.includes('/inventory/') && init?.method === 'POST') writes.push(JSON.parse(init.body as string));
    if (url.endsWith('/picks') && init?.method !== 'POST' && failPickRead) {
      failPickRead = false;
      return Promise.resolve(new Response('{}', {status:503}));
    }
    if (url.endsWith('/picks') && init?.method === 'POST' && losePickResponse) {
      return realFetch(new URL(url, base).href, init).then(response => {
        if (response.ok) { losePickResponse = false; throw new Error('Injected response loss after committed pick'); }
        return response;
      });
    }
    if (failRead && url.includes('/inventory/') && url.includes('?warehouseId=')) {
      failRead = false;
      return Promise.resolve(new Response('{}', {status: 503}));
    }
    return realFetch(new URL(url, base).href, init);
  });
  vi.stubEnv('VITE_B05_TEST_UI', 'true');
  vi.stubEnv('VITE_B06_TEST_UI', 'true');
  vi.stubEnv('VITE_B07_TEST_UI', 'true');
  vi.stubEnv('VITE_B08_TEST_UI', 'true');
  const {default: App} = await import('./App');
  render(<App/>);
  fireEvent.change(screen.getByLabelText('Utente sintetico'), {target: {value: 'operatore-alfa-sintetico'}});
  fireEvent.change(screen.getByLabelText('Password sintetica'), {target: {value: 'synthetic-alpha-password'}});
  fireEvent.click(screen.getByRole('button', {name: 'Accedi'}));
  fireEvent.click(await screen.findByRole('button', {name: 'Alfa Società Uno · Alfa Sede Nord'}, {timeout:15000}));
  await screen.findByRole('option', {name: 'Veicolo sintetico altra società'});
  for (const [label,value] of [['Soggetto a carico','11111111-3333-0000-0000-000000000001'],['Tipo commessa','11111111-5555-0000-0000-000000000001'],['Veicolo','11111111-4444-0000-0000-000000000001']])
    fireEvent.change(screen.getByLabelText(label), {target:{value}});
  fireEvent.click(screen.getByRole('button', {name:'Apri commessa'}));
  const add = await screen.findByRole('button', {name:'Aggiungi ricambio'});
  await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('Quantità ricambio'), {target:{value:'3'}});
  fireEvent.click(add);
  await screen.findByRole('heading', {name:'Prenotazione ricambio'});
  const warehouse = await screen.findByLabelText('Magazzino prenotazione');
  await screen.findByRole('option', {name:'Alfa Nord Magazzino A'});
  fireEvent.change(warehouse, {target:{value:'11111111-1111-1111-1111-111111100101'}});
  await screen.findByText('Disponibile: 2');
  fireEvent.change(screen.getByLabelText('Quantità da prenotare'), {target:{value:'3'}});
  fireEvent.click(screen.getByRole('button', {name:'Prenota quantità esplicita'}));
  await screen.findByText(/Disponibilità insufficiente/);
  expect(screen.getByText('Prenotato sulla riga: 0')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Quantità da prenotare'), {target:{value:'2.000000'}});
  failRead = true;
  fireEvent.click(screen.getByRole('button', {name:'Prenota quantità esplicita'}));
  await screen.findByText(/Stato non disponibile/);
  fireEvent.click(screen.getByRole('button', {name:'Rileggi prenotazioni'}));
  await screen.findByText('Prenotato sulla riga: 2');
  expect(screen.getByText('Fisico: 2')).toBeTruthy();
  expect(screen.getByText('Disponibile: 0')).toBeTruthy();
  expect(screen.getByText('Residuo da prenotare: 1')).toBeTruthy();
  await screen.findByRole('heading', {name:'Prelievo ricambio'});
  await screen.findByText(/Stato prelievo non disponibile/);
  expect((screen.getByRole('button', {name:'Preleva quantità esplicita'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', {name:'Rileggi prelievi'}));
  await waitFor(() => expect((screen.getByRole('button', {name:'Preleva quantità esplicita'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('Quantità da prelevare'), {target:{value:'3'}});
  fireEvent.click(screen.getByRole('button', {name:'Preleva quantità esplicita'}));
  await screen.findByText(/Quantità superiore al residuo/);
  losePickResponse = false;
  fireEvent.change(screen.getByLabelText('Quantità da prelevare'), {target:{value:'2'}});
  fireEvent.click(screen.getByRole('button', {name:'Preleva quantità esplicita'}));
  await screen.findByText('Prelevato: 2');
  await screen.findByRole('heading', {name:'Installazione ricambio'});
  const install = screen.getByRole('button', {name:'Installa quantità esplicita'});
  await waitFor(() => expect((install as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('Quantità da installare'), {target:{value:'3'}});
  fireEvent.click(install);
  await screen.findByText(/Quantità superiore al prelevato non installato/);
  fireEvent.change(screen.getByLabelText('Quantità da installare'), {target:{value:'0.000001'}});
  fireEvent.click(install);
  if (fault) {
    await screen.findByText(/Installazione registrata — consumo in attesa/);
    expect(screen.getByText('Fisico: 2')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name:'Recupera consumo'}));
  } else {
    await screen.findByText(/Installazione non confermata/);
    fireEvent.click(install);
  }
  await screen.findByText('Installato: 0.000001');
  await screen.findByText('Prelevato non installato: 1.999999');
  await screen.findByText(/Consumo confermato/);
  await screen.findByText('Fisico: 1.999999');
  expect(screen.getByText('Disponibile: 0')).toBeTruthy();
  expect(installationWrites.map(x => x.quantity)).toEqual(['3','0.000001','0.000001']);
  expect(installationWrites[1].id).toBe(installationWrites[2].id);
}, 30000);
