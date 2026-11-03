import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync } from "node:fs";
import https from "node:https";
import { syncBuiltinESMExports } from "node:module";
import { EventEmitter } from "node:events";

test(
  "SSR partial-response transport error fails closed instead of crashing the server",
  { timeout: 3000 },
  async (t) => {
    const { privateRead } = await import("../lib/private-backend");
    const fakeRequest = (
      _url: unknown,
      _options: unknown,
      callback: (response: EventEmitter & { statusCode: number }) => void,
    ) =>
      Object.assign(new EventEmitter(), {
        end() {
          queueMicrotask(() => {
            const response = Object.assign(new EventEmitter(), {
              statusCode: 200,
            });
            callback(response);
            response.emit(
              "error",
              new Error("Synthetic interrupted TLS response"),
            );
          });
        },
      });
    t.mock.method(
      https,
      "request",
      fakeRequest as unknown as typeof https.request,
    );
    syncBuiltinESMExports();
    try {
      const result = await privateRead("/auth/session", "", undefined, {
        origin: "https://api.r00.test:8443",
        host: "app.r00.test:8443",
      });
      assert.equal(result.status, 503);
    } finally {
      t.mock.restoreAll();
      syncBuiltinESMExports();
    }
  },
);
const url = new URL("../lib/private-backend.ts", import.meta.url);
test("SSR forwards only current cookie to fixed trusted HTTPS and never caches", async () => {
  const calls: unknown[] = [];
  const fn = existsSync(url)
    ? (await import(url.href)).privateRead
    : async () => ({ status: 503 });
  const get = async (...args: unknown[]) => {
    calls.push(args);
    return new Response('{"authenticated":true}', { status: 200 });
  };
  await fn("/auth/session", "one=first", get, {
    origin: "https://api.r00.test:8443",
    host: "app.r00.test:8443",
  });
  await fn("/auth/session", "two=second", get, {
    origin: "https://api.r00.test:8443",
    host: "app.r00.test:8443",
  });
  assert.equal(
    calls.length,
    2,
    "private current-request read must execute, not an empty shell",
  );
  for (const [index, call] of calls.entries()) {
    const [target, options] = call as [string, RequestInit];
    assert.equal(target, "https://api.r00.test:8443/auth/session");
    assert.equal(options.cache, "no-store");
    assert.equal(options.redirect, "manual");
    assert.deepEqual(options.headers, {
      Cookie: index === 0 ? "one=first" : "two=second",
      Host: "app.r00.test:8443",
    });
  }
});
