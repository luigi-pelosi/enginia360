import { check, record } from './contracts';
export class ApiError extends Error {
  constructor(readonly status: number, readonly code?: string) {
    super(status === 401 ? 'Sessione terminata. Accedi nuovamente.' : status === 403 ? 'Azione o scope non autorizzato. Riprova per aggiornare i permessi.' : status === 404 ? 'Risorsa non disponibile o non accessibile.' : status === 409 ? 'Conflitto: rileggi prima di un nuovo comando.' : code === 'csrf_invalid' ? 'CSRF non valido: verifica nuovamente la sessione, senza reinvio automatico.' : 'Servizio non disponibile o richiesta non valida. Riprova.');
  }
}
export async function request(path: string, body?: unknown): Promise<unknown> {
  let options: RequestInit = { credentials: 'same-origin', cache: 'no-store' };
  if (body !== undefined) {
    const csrf = record(await request('/auth/csrf'));
    check(typeof csrf.requestToken === 'string' && csrf.requestToken.length > 0);
    options = { ...options, method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf.requestToken }, body: JSON.stringify(body) };
  }
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(response.status, error?.error ?? error?.code);
  }
  return response.json();
}
