import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import B13JournalEntry from './B13JournalEntry';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const invoiceId = '11111111-7777-0000-0000-000000000001';
const entry = {
  id: '11111111-8888-0000-0000-000000000001', invoiceId, invoiceReference: 'FV-001/2026',
  entryDate: '2026-10-20', currency: 'EUR', totalDebit: '200.690000', totalCredit: '200.690000',
  difference: '0.000000', balanced: true, invoiceLinkState: 'Linked',
  lines: [
    {lineNumber: 1, accountCode: '120100', accountDescription: 'Crediti verso clienti', debit: '200.690000', credit: '0.000000'},
    {lineNumber: 2, accountCode: '700100', accountDescription: 'Ricavi prestazioni officina', debit: '0.000000', credit: '74.250000'},
    {lineNumber: 3, accountCode: '700200', accountDescription: 'Ricavi vendita ricambi', debit: '0.000000', credit: '90.250000'},
    {lineNumber: 4, accountCode: '220100', accountDescription: 'Erario c/IVA a debito', debit: '0.000000', credit: '36.190000'},
  ],
};
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), {status}));
const props = {invoiceId, token: 'synthetic', chartVersion: 1};

test('retries the same posting command after a lost response and shows the balanced entry', async () => {
  const commands: Record<string, unknown>[] = []; let calls = 0;
  vi.stubGlobal('fetch', (_url: string, init?: RequestInit) => {
    if (init?.body) commands.push(JSON.parse(init.body as string));
    return ++calls === 1 ? Promise.reject(new Error('lost')) : json(entry, 201);
  });
  render(<B13JournalEntry {...props}/>);
  const post = screen.getByRole('button', {name: 'Registra scrittura'});
  fireEvent.click(post);
  await screen.findByText(/Registrazione non confermata/);
  fireEvent.click(post);
  await screen.findByText(/Dare 200.690000 = Avere 200.690000 EUR/);
  expect(commands[1].id).toBe(commands[0].id);
  expect(screen.getByText(/collegata alla fattura confermata/)).toBeTruthy();
  expect(screen.getByText('Crediti verso clienti')).toBeTruthy();
});

test('shows the pending invoice link instead of claiming a completed registration', async () => {
  vi.stubGlobal('fetch', () => json({...entry, invoiceLinkState: 'Pending'}, 201));
  render(<B13JournalEntry {...props}/>);
  fireEvent.click(screen.getByRole('button', {name: 'Registra scrittura'}));
  await screen.findByText(/collegamento alla fattura non ancora registrato/);
});

test.each([
  {...entry, lines: entry.lines.slice(0, 2)},
  {...entry, balanced: false},
  {...entry, difference: '1.000000'},
  {...entry, lines: [...entry.lines.slice(0, 3), {...entry.lines[3], credit: '36.200000'}]},
  {...entry, lines: [{...entry.lines[0], accountCode: 'NaN'}, entry.lines[1]]},
])('refuses unbalanced, inconsistent or malformed journal contracts', async (value) => {
  vi.stubGlobal('fetch', () => json(value, 201));
  render(<B13JournalEntry {...props}/>);
  fireEvent.click(screen.getByRole('button', {name: 'Registra scrittura'}));
  await screen.findByText(/Registrazione non confermata/);
  expect(screen.queryByText(/= Avere/)).toBeNull();
});

test('a refused second posting states that the confirmed invoice is unchanged', async () => {
  vi.stubGlobal('fetch', () => json({code: 'invoice_already_posted'}, 409));
  render(<B13JournalEntry {...props}/>);
  fireEvent.click(screen.getByRole('button', {name: 'Registra scrittura'}));
  await screen.findByText(/la fattura confermata resta invariata/);
});
