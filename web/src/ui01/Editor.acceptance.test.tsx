import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import WorkshopEditor from './WorkshopEditor';
import { longDocument, prototypeCatalog, prototypePayers, prototypeVehicles } from './syntheticFixtures';

afterEach(cleanup);

test('long synthetic document exposes 100 editable rows across repeated groups with unique stable ids', () => {
    const lines = longDocument.groups.flatMap(group => group.lines);
    expect(lines).toHaveLength(100);
    expect(new Set(lines.map(line => line.id)).size).toBe(100);
    expect(longDocument.groups.length).toBeGreaterThan(1);
    expect(longDocument.payer.id).not.toBe(longDocument.vehicle.keeper);
    render(<WorkshopEditor document={longDocument} catalog={prototypeCatalog} vehicles={prototypeVehicles} payers={prototypePayers} />);
    expect(screen.getAllByRole('button', { name: /^Modifica / })).toHaveLength(100);
});

test('the last row of the long document is still editable and applies its own identity only', () => {
    const onDraftChange = vi.fn();
    const lines = longDocument.groups.flatMap(group => group.lines);
    const last = lines[lines.length - 1];
    render(<WorkshopEditor document={longDocument} catalog={prototypeCatalog} vehicles={prototypeVehicles} payers={prototypePayers} onDraftChange={onDraftChange} />);
    fireEvent.click(screen.getByRole('button', { name: `Modifica ${last.id}` }));
    fireEvent.change(screen.getByLabelText(`Descrizione ${last.id}`), { target: { value: 'Riga finale sintetica' } });
    fireEvent.click(screen.getByRole('button', { name: 'Applica riga' }));
    const emitted = onDraftChange.mock.calls[0][0].groups.flatMap((group: { lines: readonly { id: string; description: string }[] }) => group.lines);
    expect(emitted).toHaveLength(100);
    expect(emitted[emitted.length - 1]).toMatchObject({ id: last.id, description: 'Riga finale sintetica' });
    expect(emitted.filter((line: { description: string }) => line.description === 'Riga finale sintetica')).toHaveLength(1);
});

test('fixtures contain only declared synthetic data and no real contact details', () => {
    const serialized = JSON.stringify({ longDocument, prototypeCatalog, prototypeVehicles, prototypePayers });
    expect(serialized).not.toMatch(/@|\+39|\bS\.?R\.?L\.?\b|\bS\.?P\.?A\.?\b/i);
    expect(serialized.toLowerCase()).toContain('sintetic');
    expect(longDocument.operations.external).toBe('Received');
});
