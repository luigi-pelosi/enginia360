import { request } from "node:https";
// Native HTTPS preserves the explicit backend Host; undici fetch ignores Host.
const backendFetch: typeof fetch = async (input, init) =>
  new Promise((resolve, reject) => {
    const req = request(
      String(input),
      {
        method: "GET",
        servername: new URL(String(input)).hostname,
        headers: init?.headers as Record<string, string>,
        signal: init?.signal || undefined,
      },
      (res) => {
        res.on("error", reject);
        const chunks: Buffer[] = [];
        let size = 0;
        res.on("data", (chunk: Buffer) => {
          size += chunk.length;
          if (size > 1024 * 1024) {
            req.destroy(new Error("Response bound"));
            return;
          }
          chunks.push(chunk);
        });
        res.on("end", () =>
          resolve(
            new Response(Buffer.concat(chunks), {
              status: res.statusCode || 503,
            }),
          ),
        );
      },
    );
    req.on("error", reject);
    req.end();
  });
// Server-only import site is the organization server page. Never export config to client props.
export async function privateRead(
  path: string,
  cookie: string,
  get: typeof fetch = backendFetch,
  config = {
    origin: process.env.ORGANIZATION_BACKEND_ORIGIN || "",
    host: process.env.ORGANIZATION_PUBLIC_HOST || "",
  },
) {
  if (
    ![
      "/auth/session",
      "/api/v1/platform/administration-eligibility",
      "/api/v1/platform/tenants",
    ].includes(path) &&
    !/^\/api\/v1\/platform\/tenants\/[a-f0-9-]{36}$/.test(path)
  )
    throw new Error("Nonfinite backend read");
  try {
    const origin = new URL(config.origin);
    if (
      origin.protocol !== "https:" ||
      origin.username ||
      origin.password ||
      origin.pathname !== "/" ||
      origin.search ||
      origin.hash ||
      !config.host ||
      /[\s/]/.test(config.host)
    )
      return { status: 503, value: null };
    const response = await get(origin.origin + path, {
      headers: { Cookie: cookie, Host: config.host },
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(8000),
    });
    return {
      status: response.status,
      value: response.ok ? await response.json() : null,
    };
  } catch {
    return { status: 503, value: null };
  }
}
