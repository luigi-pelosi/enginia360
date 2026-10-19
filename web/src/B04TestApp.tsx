import { FormEvent, ReactNode, useRef, useState } from "react";

type Context = {
  legalEntityId: string;
  legalEntityName: string;
  siteId: string;
  siteName: string;
};
type Choice = { id: string; label: string };
type Payer = { id: string; legalName: string };
type DocumentType = {
  id: string;
  name: string;
  version: number;
  directCreationEnabled: boolean;
};
type Order = {
  id: string;
  legalEntityId: string;
  siteId: string;
  payerId: string;
  vehicleId: string;
  vehicleHolderId: string;
  documentTypeId: string;
  configurationVersion: number;
  isCustomerOrder: true;
};
const uuid = (x: unknown): x is string =>
  typeof x === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(x);
const text = (x: unknown): x is string =>
  typeof x === "string" && x.trim().length > 0 && x.length <= 200;
const record = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null;
function list<T>(
  value: unknown,
  valid: (x: Record<string, unknown>) => boolean,
): T[] {
  if (!Array.isArray(value) || !value.every((x) => record(x) && valid(x)))
    throw new Error("Invalid response");
  return value as T[];
}
function order(value: unknown): Order {
  if (
    !record(value) ||
    ![
      "id",
      "legalEntityId",
      "siteId",
      "payerId",
      "vehicleId",
      "vehicleHolderId",
      "documentTypeId",
    ].every((k) => uuid(value[k])) ||
    !Number.isInteger(value.configurationVersion) ||
    Number(value.configurationVersion) < 1 ||
    value.isCustomerOrder !== true
  )
    throw new Error("Invalid order");
  return value as Order;
}
export default function B04TestApp({ commercial }: { commercial?: (order: Order, token: string) => ReactNode } = {}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [contexts, setContexts] = useState<Context[]>([]);
  const [context, setContext] = useState<Context>();
  const [vehicles, setVehicles] = useState<Choice[]>([]);
  const [payers, setPayers] = useState<Payer[]>([]);
  const [types, setTypes] = useState<DocumentType[]>([]);
  const [payer, setPayer] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [type, setType] = useState("");
  const [saved, setSaved] = useState<Order>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const pending = useRef<{ key: string; id: string } | undefined>(undefined);
  async function api(
    path: string,
    bearer = token,
    payload?: unknown,
  ): Promise<unknown> {
    const response = await fetch(path, {
      method: payload === undefined ? "GET" : "POST",
      headers: {
        Authorization: `Bearer ${bearer}`,
        "Content-Type": "application/json",
      },
      ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
    });
    if (!response.ok) throw new Error("Request denied");
    return response.json();
  }
  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api("/api/v1/development/login", "", {
        username,
        password,
      });
      if (
        !record(result) ||
        typeof result.accessToken !== "string" ||
        !result.accessToken
      )
        throw new Error();
      const rows = list<Context>(
        await api("/api/v1/workshop/contexts", result.accessToken),
        (x) =>
          uuid(x.legalEntityId) &&
          text(x.legalEntityName) &&
          uuid(x.siteId) &&
          text(x.siteName),
      );
      setContexts(rows);
      setToken(result.accessToken);
      setPassword("");
    } catch {
      setError(
        "Accesso non riuscito. Riprova con una identità sintetica autorizzata.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function select(value: Context) {
    const version = ++generation.current;
    setContext(value);
    setPayer("");
    setVehicle("");
    setType("");
    setSaved(undefined);
    setVehicles([]);
    setPayers([]);
    setTypes([]);
    setError("");
    setBusy(true);
    pending.current = undefined;
    try {
      const query = `?legalEntityId=${value.legalEntityId}&siteId=${value.siteId}`;
      const v = list<Choice>(
        await api("/api/v1/workshop/vehicles" + query),
        (x) => uuid(x.id) && text(x.label),
      );
      const p = list<Payer>(
        await api(
          "/api/v1/counterparties?legalEntityId=" + value.legalEntityId,
        ),
        (x) => uuid(x.id) && text(x.legalName),
      );
      const t = list<DocumentType>(
        await api("/api/v1/workshop/document-types" + query),
        (x) =>
          uuid(x.id) &&
          text(x.name) &&
          Number.isInteger(x.version) &&
          Number(x.version) > 0 &&
          typeof x.directCreationEnabled === "boolean",
      );
      if (version === generation.current) {
        setVehicles(v);
        setPayers(p);
        setTypes(t);
      }
    } catch {
      if (version === generation.current)
        setError(
          "Selezione non disponibile. Riprova selezionando un contesto autorizzato.",
        );
    } finally {
      if (version === generation.current) setBusy(false);
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    const configuration = types.find(
      (x) => x.id === type && x.directCreationEnabled,
    );
    if (!context || !configuration || !payer || !vehicle || busy) return;
    const version = generation.current;
    setBusy(true);
    setError("");
    setSaved(undefined);
    const values = {
      legalEntityId: context.legalEntityId,
      siteId: context.siteId,
      documentTypeId: type,
      configurationVersion: configuration.version,
      payerId: payer,
      vehicleId: vehicle,
    };
    const key = JSON.stringify(values);
    if (pending.current?.key !== key)
      pending.current = { key, id: crypto.randomUUID() };
    try {
      const created = order(
        await api("/api/v1/workshop/orders", token, {
          ...values,
          id: pending.current.id,
        }),
      );
      const read = order(await api("/api/v1/workshop/orders/" + created.id));
      if (version === generation.current) setSaved(read);
    } catch {
      if (version === generation.current)
        setError(
          "Commessa non confermata. Riprova senza cambiare i campi per recuperare lo stesso tentativo; se la configurazione è cambiata, riseleziona il contesto.",
        );
    } finally {
      if (version === generation.current) setBusy(false);
    }
  }
  return (
    <main>
      <h1>Commessa diretta · prova privata {commercial ? "B05" : "B04"}</h1>
      <p>
        Solo dati e identità sintetici. Commessa già ordine cliente. {commercial ? "Valori del solo caso 001, nessuna emissione fiscale." : "Nessuna riga o fiscalità."}
      </p>
      {!token ? (
        <form onSubmit={login}>
          <label>
            Utente sintetico
            <input
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label>
            Password sintetica
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button disabled={busy}>Accedi</button>
        </form>
      ) : (
        <>
          {contexts.length === 0 && (
            <p>
              Nessun contesto officina autorizzato. Contatta il referente degli
              accessi.
            </p>
          )}
          <section aria-label="Contesti autorizzati">
            {contexts.map((x) => (
              <button
                key={x.legalEntityId + x.siteId}
                disabled={busy}
                onClick={() => void select(x)}
              >
                {x.legalEntityName} · {x.siteName}
              </button>
            ))}
          </section>
          {context && (
            <form onSubmit={save}>
              <p>
                Società: {context.legalEntityName} · Sede unica:{" "}
                {context.siteName}
              </p>
              <label>
                Tipo commessa
                <select
                  required
                  value={type}
                  disabled={busy}
                  onChange={(e) => setType(e.target.value)}
                >
                  <option value="">Seleziona</option>
                  {types.map((x) => (
                    <option
                      key={x.id}
                      value={x.id}
                      disabled={!x.directCreationEnabled}
                    >
                      {x.name} · versione {x.version}
                      {!x.directCreationEnabled &&
                        " · creazione diretta disabilitata"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Soggetto a carico
                <select
                  required
                  value={payer}
                  disabled={busy}
                  onChange={(e) => setPayer(e.target.value)}
                >
                  <option value="">Seleziona</option>
                  {payers.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.legalName}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Veicolo
                <select
                  required
                  value={vehicle}
                  disabled={busy}
                  onChange={(e) => setVehicle(e.target.value)}
                >
                  <option value="">Seleziona</option>
                  {vehicles.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.label}
                    </option>
                  ))}
                </select>
              </label>
              <p>Il veicolo non modifica il soggetto a carico selezionato.</p>
              <button disabled={busy || !payer || !vehicle || !type}>
                Apri commessa
              </button>
            </form>
          )}
          {saved && (
            <section role="status">
              <h2>Commessa · ordine cliente</h2>
              <p>Identificativo: {saved.id}</p>
              <p>Soggetto a carico: {saved.payerId}</p>
              <p>Intestatario veicolo: {saved.vehicleHolderId}</p>
              <p>Configurazione: versione {saved.configurationVersion}</p>
              {commercial?.(saved, token)}
            </section>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
