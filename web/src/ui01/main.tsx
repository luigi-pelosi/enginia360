// Opt-in UI01.a prototype entry. Never imported by the default bootstrap bundle.
import { StrictMode, useState } from 'react';
import { createRoot } from 'react-dom/client';
import WorkshopEditor from './WorkshopEditor';
import { emptyDocument, longDocument, prototypeCatalog, prototypePayers, prototypeVehicles, shortDocument } from './syntheticFixtures';
import type { EditorDocument } from './contracts';
import './editor.css';

const scenarios: Record<string, { label: string; document: EditorDocument; state?: 'ready' | 'loading' | 'error' }> = {
    short: { label: 'Documento breve', document: shortDocument },
    long: { label: 'Documento lungo (100 righe)', document: longDocument },
    empty: { label: 'Documento vuoto', document: emptyDocument },
    loading: { label: 'Stato caricamento', document: shortDocument, state: 'loading' },
    error: { label: 'Stato errore', document: shortDocument, state: 'error' },
};

function Prototype() {
    const [key, setKey] = useState<keyof typeof scenarios>('long');
    const scenario = scenarios[key];
    return <>
        <div className="ui01-scenarios">
            <label htmlFor="ui01-scenario">Scenario sintetico</label>
            <select id="ui01-scenario" value={key} onChange={event => setKey(event.target.value)}>
                {Object.entries(scenarios).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}
            </select>
        </div>
        <WorkshopEditor key={key} document={scenario.document} state={scenario.state} catalog={prototypeCatalog} vehicles={prototypeVehicles} payers={prototypePayers} />
    </>;
}

createRoot(document.getElementById('ui01-root')!).render(<StrictMode><Prototype /></StrictMode>);
