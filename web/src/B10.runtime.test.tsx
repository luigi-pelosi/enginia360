import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
const base = import.meta.env.VITE_B10_HTTP_BASE as string | undefined;
const simulator = import.meta.env.VITE_B10_SIMULATOR as string | undefined;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules(); });

async function eventually(text: RegExp | string, reload: () => void, seconds = 25) {
  const deadline = Date.now() + seconds * 1000;
  for (;;) {
    try { return await screen.findByText(text, {}, {timeout: 500}); }
    catch (error) { if (Date.now() > deadline) throw error; reload(); }
  }
}

test.skipIf(!base || !simulator)("B10 real DOM/HTTP closure gate, lost closure response, durable request, received vs confirmed, administrative closure", async () => {
  const realFetch = globalThis.fetch;
  await realFetch(`${simulator}/control/mode`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({mode: 'receive'})});
  const writes: {path: string; body: Record<string, unknown>}[] = [];
  let loseClosureResponse = true;
  vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
    if (init?.method === 'POST' && /\/(technical-closure|administrative-requests|administrative-closure)$/.test(url)) {
      writes.push({path: url.split('/').pop()!, body: JSON.parse(init.body as string) as Record<string, unknown>});
      return realFetch(new URL(url, base).href, init).then(response => {
        if (url.endsWith('/technical-closure') && response.ok && loseClosureResponse) { loseClosureResponse = false; throw new Error('Injected lost committed closure response'); }
        return response;
      });
    }
    return realFetch(new URL(url, base).href, init);
  });
  for (const flag of ['VITE_B05_TEST_UI','VITE_B06_TEST_UI','VITE_B07_TEST_UI','VITE_B08_TEST_UI','VITE_B09_TEST_UI','VITE_B10_TEST_UI']) vi.stubEnv(flag, 'true');
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
  fireEvent.change(screen.getByLabelText('Articolo ricambio'), {target:{value:'11111111-7777-0000-0000-000000000003'}});
  fireEvent.change(screen.getByLabelText('Quantità ricambio'), {target:{value:'2'}});
  fireEvent.click(add);
  await screen.findByText(/Componente sintetico con carcassa · 2/);
  const warehouse = await screen.findByLabelText('Magazzino prenotazione');
  await screen.findByRole('option', {name:'Alfa Nord Magazzino A'});
  fireEvent.change(warehouse, {target:{value:'11111111-1111-1111-1111-111111100101'}});
  await screen.findByText(/^Disponibile: /);
  fireEvent.change(screen.getByLabelText('Quantità da prenotare'), {target:{value:'2'}});
  fireEvent.click(screen.getByRole('button', {name:'Prenota quantità esplicita'}));
  await screen.findByText('Prenotato sulla riga: 2');
  const pick = await screen.findByRole('button', {name:'Preleva quantità esplicita'});
  await waitFor(() => expect((pick as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('Quantità da prelevare'), {target:{value:'2'}});
  fireEvent.click(pick);
  await screen.findByText('Prelevato: 2');
  const install = await screen.findByRole('button', {name:'Installa quantità esplicita'});
  await waitFor(() => expect((install as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('Quantità da installare'), {target:{value:'2'}});
  fireEvent.click(install);
  await screen.findByText('Residuo carcassa da rientrare: 2');
  const reload = () => fireEvent.click(screen.getByRole('button', {name: 'Rileggi stato amministrativo'}));
  await screen.findByText('Commessa aperta: chiusura tecnica non registrata');
  const close = screen.getByRole('button', {name: 'Chiudi tecnicamente'});
  await waitFor(() => expect((close as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(close);
  await screen.findByText('Chiusura tecnica rifiutata: carcassa da rientrare. Nessuna chiusura registrata.');
  fireEvent.change(screen.getByLabelText('Descrizione carcassa'), {target:{value:'Carcassa sostituita sintetica'}});
  fireEvent.change(screen.getByLabelText('Quantità carcassa'), {target:{value:'2'}});
  fireEvent.click(screen.getByRole('button', {name:'Registra rientro carcassa'}));
  await screen.findByText('Residuo carcassa da rientrare: 0');
  await waitFor(() => expect((close as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(close);
  await screen.findByText(/Operazione non confermata/);
  fireEvent.click(close);
  await screen.findByText('Completata tecnicamente — richiesta amministrativa da inviare');
  const send = screen.getByRole('button', {name: 'Invia al gestionale amministrativo'});
  await waitFor(() => expect((send as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(send);
  await screen.findByText('Completata tecnicamente — in attesa di conferma amministrativa');
  await eventually('Consegna al gestionale: ricevuta (sola acquisizione) · tentativi 1', reload);
  expect((screen.getByRole('button', {name: 'Chiudi amministrativamente'}) as HTMLButtonElement).disabled).toBe(true);
  const requestId = writes.find(x => x.path === 'administrative-requests')!.body.id as string;
  expect((await realFetch(`${simulator}/control/complete/${requestId}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})).status).toBe(200);
  await eventually(/^Confermata dal gestionale amministrativo · riferimento AMM-SIM-\d{6}$/, reload);
  const closeAdministratively = screen.getByRole('button', {name: 'Chiudi amministrativamente'});
  await waitFor(() => expect((closeAdministratively as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(closeAdministratively);
  await screen.findByText(/^Chiusa amministrativamente · riferimento AMM-SIM-\d{6}$/);
  expect(writes.map(x => x.path)).toEqual(['technical-closure', 'technical-closure', 'technical-closure', 'administrative-requests', 'administrative-closure']);
  // A refused command records nothing, so its ID is safely reused; the lost committed response is replayed with the same ID.
  expect(new Set(writes.slice(0, 3).map(x => x.body.id)).size).toBe(1);
  expect(writes[1].body).toEqual({id: writes[1].body.id, expectedRevision: 1});
}, 90000);
