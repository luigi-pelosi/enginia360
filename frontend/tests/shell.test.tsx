import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { existsSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";

// Empty renderer is the explicit pre-shell baseline, not an auth or data mock.
// Once implemented, exercise the real React component and its navigation.
const shellUrl = new URL("../components/shell.tsx", import.meta.url);
test("SSR shell exposes seven domain links and an honest unauthenticated boundary", async () => {
    const Shell = existsSync(shellUrl)
        ? (await import(shellUrl.href)).Shell
        : () => null;
    const html = renderToStaticMarkup(
        <Shell>
            <h1>Area di lavoro</h1>
        </Shell>,
    );
    assert.match(
        html,
        /aria-label="Navigazione principale"/,
        "SSR must expose usable domain navigation",
    );
    for (const slug of [
        "identity",
        "organization",
        "counterparties",
        "catalog",
        "inventory",
        "document-types",
        "documents",
    ]) {
        assert.match(html, new RegExp(`href="/domains/${slug}"`));
    }
    assert.match(html, /Accesso non disponibile/);
    assert.match(html, /Nessun contesto aziendale attivo/);
    assert.doesNotMatch(html, /SUPER ADMIN|tenantId|Bearer|Accedi come/);
});
