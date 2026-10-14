import { useEffect, useState } from 'react';

type ConnectionState = 'loading' | 'available' | 'unavailable';

export default function App() {
    const [connection, setConnection] = useState<ConnectionState>('loading');
    useEffect(() => {
        const controller = new AbortController();
        fetch('/api/v1/system/status', { signal: controller.signal })
            .then(async response => {
                if (!response.ok) throw new Error('Status request failed');
                const status: unknown = await response.json();
                if (typeof status !== 'object' || status === null
                    || !('product' in status) || status.product !== 'Enginia360'
                    || !('stage' in status) || status.stage !== 'bootstrap'
                    || !('foundationDossierApproved' in status) || status.foundationDossierApproved !== false
                    || !('businessCapabilitiesAvailable' in status) || status.businessCapabilitiesAvailable !== false) {
                    throw new Error('Unexpected bootstrap status');
                }
                setConnection('available');
            })
            .catch(() => { if (!controller.signal.aborted) setConnection('unavailable'); });
        return () => controller.abort();
    }, []);

    return <main>
        <header><a className="brand" href="/" aria-label="Enginia360, pagina iniziale"><span className="mark">E</span> Enginia360</a><span className="badge">BOOTSTRAP TECNICO</span></header>
        <section className="hero">
            <p className="eyebrow">IL PUNTO DI PARTENZA</p>
            <h1>Enginia360<span>Una base concreta.<br />Un percorso da costruire.</span></h1>
            <p className="intro">La piattaforma per il futuro della gestione post-vendita. Oggi è disponibile soltanto l’infrastruttura tecnica iniziale.</p>
        </section>
        <section className="status-card" aria-labelledby="status-title">
            <div><p className="eyebrow">STATO DEL SISTEMA</p><h2 id="status-title">Connessione alla piattaforma</h2></div>
            <p role="status" className={`connection ${connection}`}><span className="dot" />{connection === 'loading' ? 'Verifica in corso…' : connection === 'available' ? 'API disponibile' : 'API non disponibile'}</p>
        {connection === 'unavailable' && <p>Ricarica la pagina per riprovare. Se il problema persiste, consulta i log del servizio.</p>}</section>
        <section className="scope"><h2>Trasparenza, fin dall’inizio.</h2><p>Dossier di fondazione non approvato. Nessuna funzionalità aziendale disponibile.</p><p>Questa pagina non gestisce clienti, veicoli, commesse, identità o tenant. Non contiene dati dimostrativi.</p></section>
        <footer><span>Enginia360 · Fondamenta tecniche</span><a href="/openapi/v1.json">Contratto API · OpenAPI</a></footer>
    </main>;
}
