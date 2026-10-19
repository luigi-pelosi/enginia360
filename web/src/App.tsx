import { FormEvent, useEffect, useState } from "react";
import B03TestApp from "./B03TestApp";
import B04TestApp from "./B04TestApp";
import B05TestApp from "./B05TestApp";

type ConnectionState = "loading" | "available" | "unavailable";
type Context = {
    tenantId: string;
    tenantName: string;
    legalEntityId: string;
    legalEntityName: string;
    siteId: string;
    siteName: string;
    warehouseId: string;
    warehouseName: string;
    capabilityEnabled: boolean;
};
type Note = { id: string; message: string };

function Brand({ badge }: { badge: string }) {
    return (
        <header>
            <a
                className="brand"
                href="/"
                aria-label="Enginia360, pagina iniziale"
            >
                <span className="mark">E</span> Enginia360
            </a>
            <span className="badge">{badge}</span>
        </header>
    );
}

function BootstrapApp() {
    const [connection, setConnection] = useState<ConnectionState>("loading");
    useEffect(() => {
        const controller = new AbortController();
        fetch("/api/v1/system/status", { signal: controller.signal })
            .then(async (response) => {
                if (!response.ok) throw new Error("Status request failed");
                const status: unknown = await response.json();
                if (
                    typeof status !== "object" ||
                    status === null ||
                    !("product" in status) ||
                    status.product !== "Enginia360" ||
                    !("stage" in status) ||
                    status.stage !== "bootstrap" ||
                    !("foundationDossierApproved" in status) ||
                    status.foundationDossierApproved !== false ||
                    !("businessCapabilitiesAvailable" in status) ||
                    status.businessCapabilitiesAvailable !== false
                ) {
                    throw new Error("Unexpected bootstrap status");
                }
                setConnection("available");
            })
            .catch(() => {
                if (!controller.signal.aborted) setConnection("unavailable");
            });
        return () => controller.abort();
    }, []);

    return (
        <main>
            <Brand badge="BOOTSTRAP TECNICO" />
            <section className="hero">
                <p className="eyebrow">IL PUNTO DI PARTENZA</p>
                <h1>
                    Enginia360
                    <span>
                        Una base concreta.
                        <br />
                        Un percorso da costruire.
                    </span>
                </h1>
                <p className="intro">
                    La piattaforma per il futuro della gestione post-vendita.
                    Oggi è disponibile soltanto l’infrastruttura tecnica
                    iniziale.
                </p>
            </section>
            <section className="status-card" aria-labelledby="status-title">
                <div>
                    <p className="eyebrow">STATO DEL SISTEMA</p>
                    <h2 id="status-title">Connessione alla piattaforma</h2>
                </div>
                <p role="status" className={`connection ${connection}`}>
                    <span className="dot" />
                    {connection === "loading"
                        ? "Verifica in corso…"
                        : connection === "available"
                          ? "API disponibile"
                          : "API non disponibile"}
                </p>
                {connection === "unavailable" && (
                    <p>
                        Ricarica la pagina per riprovare. Se il problema
                        persiste, consulta i log del servizio.
                    </p>
                )}
            </section>
            <section className="scope">
                <h2>Trasparenza, fin dall’inizio.</h2>
                <p>
                    Dossier di fondazione non approvato. Nessuna funzionalità
                    aziendale disponibile.
                </p>
                <p>
                    Questa pagina non gestisce clienti, veicoli, commesse,
                    identità o tenant. Non contiene dati dimostrativi.
                </p>
            </section>
            <footer>
                <span>Enginia360 · Fondamenta tecniche</span>
                <a href="/openapi/v1.json">Contratto API · OpenAPI</a>
            </footer>
        </main>
    );
}

function B02TestApp() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [token, setToken] = useState("");
    const [contexts, setContexts] = useState<Context[]>([]);
    const [selected, setSelected] = useState<Context>();
    const [message, setMessage] = useState("");
    const [note, setNote] = useState<Note>();
    const [error, setError] = useState("");
    const auth = (value = token) => ({ Authorization: `Bearer ${value}` });
    async function login(event: FormEvent) {
        event.preventDefault();
        setError("");
        try {
            const response = await fetch("/api/v1/development/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });
            if (!response.ok) throw new Error();
            const body = (await response.json()) as { accessToken: string };
            setToken(body.accessToken);
            const contextsResponse = await fetch(
                "/api/v1/organization/contexts",
                { headers: auth(body.accessToken) },
            );
            if (!contextsResponse.ok) throw new Error();
            setContexts((await contextsResponse.json()) as Context[]);
        } catch {
            setError("Accesso sintetico non riuscito.");
        }
    }
    async function save(event: FormEvent) {
        event.preventDefault();
        if (!selected) return;
        setError("");
        try {
            const response = await fetch("/api/v1/organization/context-notes", {
                method: "POST",
                headers: { ...auth(), "Content-Type": "application/json" },
                body: JSON.stringify({ ...selected, message }),
            });
            if (!response.ok) throw new Error();
            const created = (await response.json()) as Note;
            const read = await fetch(
                `/api/v1/organization/context-notes/${created.id}`,
                { headers: auth() },
            );
            if (!read.ok) throw new Error();
            setNote((await read.json()) as Note);
        } catch {
            setError("Impossibile salvare o rileggere la nota.");
        }
    }
    return (
        <main>
            <Brand badge="B02 · SOLO SVILUPPO PRIVATO" />
            <section className="hero">
                <p className="eyebrow">CONTESTO ORGANIZZATIVO AUTORIZZATO</p>
                <h1>Seleziona il tuo contesto operativo.</h1>
                <p className="intro">
                    Percorso sintetico B02. Non usare credenziali o dati reali.
                </p>
            </section>
            {!token ? (
                <form className="status-card form" onSubmit={login}>
                    <h2>Accesso sintetico</h2>
                    <label>
                        Utente sintetico
                        <input
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                        />
                    </label>
                    <label>
                        Password sintetica
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </label>
                    <button>Accedi</button>
                </form>
            ) : (
                <>
                    <section className="scope">
                        <h2>Contesti autorizzati</h2>
                        {contexts.map((context) => (
                            <label
                                className="context"
                                key={`${context.legalEntityId}-${context.warehouseId}`}
                            >
                                <input
                                    type="radio"
                                    name="context"
                                    disabled={!context.capabilityEnabled}
                                    aria-label={`${context.legalEntityName}, ${context.siteName}, ${context.warehouseName}`}
                                    onChange={() => setSelected(context)}
                                />
                                <span>
                                    <strong>{context.legalEntityName}</strong>
                                    <br />
                                    {context.siteName} · {context.warehouseName}
                                </span>
                                {!context.capabilityEnabled && (
                                    <em>Capability disabilitata</em>
                                )}
                            </label>
                        ))}
                    </section>
                    {selected && (
                        <form className="status-card form" onSubmit={save}>
                            <h2>Nota persistita minima</h2>
                            <label>
                                Nota
                                <textarea
                                    value={message}
                                    onChange={(e) => setMessage(e.target.value)}
                                    maxLength={200}
                                    required
                                />
                            </label>
                            <button>Salva nota</button>
                            {note && <p role="status">{note.message}</p>}
                        </form>
                    )}
                </>
            )}
            {error && (
                <p role="alert" className="error">
                    {error}
                </p>
            )}
            <footer>B02 · dati esclusivamente sintetici</footer>
        </main>
    );
}

export default function App() {
    if (import.meta.env.VITE_B05_TEST_UI === "true") return <B05TestApp />;
    if (import.meta.env.VITE_B04_TEST_UI === "true") return <B04TestApp />;
    if (import.meta.env.VITE_B03_TEST_UI === "true") return <B03TestApp />;
    return import.meta.env.VITE_B02_TEST_UI === "true" ? (
        <B02TestApp />
    ) : (
        <BootstrapApp />
    );
}
