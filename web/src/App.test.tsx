import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import App from './App';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('fetches real API status and states bootstrap limitations in Italian', async () => {
    const fetchStatus = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ product: 'Enginia360', stage: 'bootstrap', foundationDossierApproved: false, businessCapabilitiesAvailable: false }) });
    vi.stubGlobal('fetch', fetchStatus);
    render(<App />);
    expect(await screen.findByText('API disponibile')).toBeTruthy();
    expect(fetchStatus).toHaveBeenCalledWith('/api/v1/system/status', expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(screen.getByText(/Dossier di fondazione non approvato/)).toBeTruthy();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Enginia360');
});

test('shows an actionable failure instead of a false available state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    render(<App />);
    expect(await screen.findByText('API non disponibile')).toBeTruthy();
    expect(screen.getByText(/Ricarica la pagina per riprovare/)).toBeTruthy();
});

test.each([
    { ok: false, json: async () => ({}) },
    { ok: true, json: async () => ({ product: 'Other' }) },
])('does not report availability for an invalid status response', async response => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
    render(<App />);
    expect(await screen.findByText('API non disponibile')).toBeTruthy();
});
