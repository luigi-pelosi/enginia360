import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
const url = new URL("../components/tenant-role-workspace.tsx", import.meta.url);
test("tenant role SSR provides real federated entry and no anonymous admin controls", async () => {
  const View = existsSync(url)
    ? (await import(url.href)).TenantRoleWorkspace
    : () => null;
  const html = renderToStaticMarkup(
    <View initial={{ status: 401, data: null, tenants: [] }} />,
  );
  assert.match(html, /Gestione utenti, ruoli e permessi/);
  assert.match(html, /Accedi con identità federata/);
  assert.doesNotMatch(
    html,
    /Salva permesso|Salva ruolo|Concedi gestione utenti/,
  );
});
test("delegate SSR exposes finite permission role and existing membership assignment without subdelegation", async () => {
  const View = existsSync(url)
    ? (await import(url.href)).TenantRoleWorkspace
    : () => null;
  const data = {
    state: "ok",
    mode: "delegate",
    tenantId: "aaaaaaaa-0000-0000-0000-000000000001",
    actions: ["organization-context.read", "organization-context.write"],
    memberships: [],
    permissions: [],
    roles: [],
    assignments: [],
    warehouses: [],
  };
  const html = renderToStaticMarkup(
    <View initial={{ status: 200, data, tenants: [] }} />,
  );
  assert.match(html, /Salva permesso/);
  assert.match(html, /Salva ruolo/);
  assert.match(html, /Assegna ruolo/);
  assert.doesNotMatch(html, /Concedi gestione utenti/);
});
test("identity domain exposes bounded real user administration entry", async () => {
  const Page = (await import("../app/domains/[domain]/page")).default;
  const html = renderToStaticMarkup(
    await Page({ params: Promise.resolve({ domain: "identity" }) }),
  );
  assert.match(html, /href="\/users"/);
});
test("SSR transport permits only finite role reads with current Cookie and no shared cache", async () => {
  const { privateRead } = await import("../lib/private-backend");
  const paths = [
    "/api/v1/platform/tenant-roles/workspace",
    "/api/v1/platform/tenant-roles/aaaaaaaa-0000-0000-0000-000000000001",
  ];
  for (const path of paths) {
    let seen = false;
    const get: typeof fetch = async (url, init) => {
      seen = true;
      assert.equal(String(url), "https://backend.test" + path);
      assert.deepEqual(init?.headers, {
        Cookie: "synthetic-session",
        Host: "public.test",
      });
      assert.equal(init?.cache, "no-store");
      return Response.json({ state: "ok" });
    };
    const result = await privateRead(path, "synthetic-session", get, {
      origin: "https://backend.test",
      host: "public.test",
    });
    assert.equal(result.status, 200);
    assert.equal(seen, true);
  }
});

test("membership SSR separates access state and exact target from administrative delegations", async () => {
  const { TenantRoleWorkspace } = await import("../components/tenant-role-workspace");
  const html = renderToStaticMarkup(<TenantRoleWorkspace initial={{ status: 200, tenants: [], data: {
    state: "ok", mode: "delegate", tenantId: "aaaaaaaa-0000-0000-0000-000000000001",
    actions: [], permissions: [], roles: [], assignments: [], warehouses: [],
    memberships: [{membershipId: "bbbbbbbb-0000-0000-0000-000000000001", internalIdentityId: "cccccccc-0000-0000-0000-000000000001",
      bindingHash: "a".repeat(64), active: true, resourceId: null, revision: 1,
      accessEnabled: false, accessRevision: 7, organizationDelegationActive: true,
      isCurrentIdentity: true, canEnableAccess: false}]
  } }} />);
  assert.match(html, /Accesso al tenant: disabilitato/);
  assert.match(html, /revisione accesso 7/);
  assert.match(html, /Delega gestione utenti: attiva/);
  assert.match(html, /Delega struttura: attiva/);
  assert.match(html, /bbbbbbbb-0000-0000-0000-000000000001/);
  assert.match(html, /disabilitando il proprio accesso/);
  assert.match(html, /ripristino richiede il SUPER ADMIN/);
  assert.match(html, /disabled=""[^>]*>Abilita accesso al tenant/);
});
