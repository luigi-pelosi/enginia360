import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
const url = new URL(
  "../components/organization-workspace.tsx",
  import.meta.url,
);
test("SSR organization denies anonymous without leaking controls", async () => {
  const View = existsSync(url)
    ? (await import(url.href)).OrganizationWorkspace
    : () => null;
  const html = renderToStaticMarkup(
    <View initial={{ status: 401, tenants: [], hierarchy: null }} />,
  );
  assert.match(html, /Accedi con identità federata/);
  assert.doesNotMatch(html, /Nuovo tenant/);
});

test("SSR empty authorized directory offers creation without inventing a tenant", async () => {
  const View = (await import(url.href)).OrganizationWorkspace;
  const html = renderToStaticMarkup(
    <View initial={{ status: 200, tenants: [], hierarchy: null }} />,
  );
  assert.match(html, /Nessun tenant disponibile/);
  assert.match(html, /Nuovo tenant/);
});
test("SSR ordinary actor has no organization controls", async () => {
  const View = (await import(url.href)).OrganizationWorkspace;
  const html = renderToStaticMarkup(
    <View initial={{ status: 403, tenants: [], hierarchy: null }} />,
  );
  assert.match(html, /Autorità amministrativa assente o revocata/);
  assert.doesNotMatch(html, /Nuovo tenant|Tenant destinatario/);
});

test("owner SSR selected tenant exposes existing membership delegation selector", async () => {
  const View = (await import(url.href)).OrganizationWorkspace;
  const tenant = { id: "aaaaaaaa-0000-0000-0000-000000000001", name: "Synthetic", revision: 1 };
  const html = renderToStaticMarkup(<View initial={{ status: 200, tenants: [tenant], hierarchy: { tenant, companies: [], sites: [], warehouses: [] } }} />);
  assert.match(html, /Delega struttura organizzativa/);
  assert.match(html, /Membership esistente/);
});
test("delegate SSR hides global tenant commands and all delegation controls", async () => {
  const View = (await import(url.href)).OrganizationWorkspace;
  const tenant = { id: "aaaaaaaa-0000-0000-0000-000000000001", name: "Synthetic", revision: 1 };
  const html = renderToStaticMarkup(<View initial={{ status: 200, mode: "delegate", tenants: [tenant], hierarchy: { tenant, companies: [], sites: [], warehouses: [] } }} />);
  assert.match(html, /Delega organizzativa verificata/);
  assert.match(html, /Nuova società/);
  assert.doesNotMatch(html, /Nuovo tenant|Rinomina tenant|Delega struttura organizzativa/);
});

test("organization domain exposes real authenticated entry without implying a business grant", async () => {
  const Page = (await import("../app/domains/[domain]/page")).default;
  const html = renderToStaticMarkup(
    await Page({ params: Promise.resolve({ domain: "organization" }) }),
  );
  assert.match(
    html,
    /href="\/organization"/,
    "organization domain must expose the implemented workspace",
  );
});
