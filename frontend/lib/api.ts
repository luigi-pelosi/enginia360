export class ApiError extends Error {
  code: string;
  status: number;
  field?: string;
  constructor(code: string, status: number, field?: string) {
    super(code);
    this.code = code;
    this.status = status;
    this.field = field;
  }
}
let csrf: string | null = null;
export async function refreshCsrf() {
  const response = await fetch("/api/auth/csrf", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError("server_error", response.status);
  csrf = (await response.json()).token;
  return csrf;
}
export async function api<T = unknown>(
  path: string,
  method = "GET",
  body?: unknown,
  options: {signal?: AbortSignal} = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") {
    await refreshCsrf();
    headers["X-CSRF-TOKEN"] = csrf!;
    if (body !== undefined) headers["Content-Type"] = "application/json";
  }
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: options.signal,
    });
  } catch {
    throw new ApiError("network_error", 0);
  }
  if (!response.ok) {
    let code = "server_error";
    let field: string | undefined;
    try {
      const error = await response.json();
      if (typeof error.code === "string" && error.code) code = error.code;
      if (typeof error.field === "string") field = error.field;
    } catch {}
    throw new ApiError(code, response.status, field);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
