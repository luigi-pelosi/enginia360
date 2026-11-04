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
        assert.match(html, new RegExp(["counterparties", "catalog", "document-types"].includes(slug) ? `href="/${slug}"` : `href="/domains/${slug}"`));
    }
    assert.match(html, /Accesso non disponibile/);
    assert.match(html, /Nessun contesto aziendale attivo/);
    assert.doesNotMatch(html, /SUPER ADMIN|tenantId|Bearer|Accedi come/);
});

test("SSR session footer distinguishes protected administration from isolated pending onboarding", async () => {
    const { SessionBoundary } = await import(shellUrl.href);
    for (const pathname of ["/organization", "/users", "/onboarding-admin", "/counterparties", "/catalog", "/document-types"]) {
        const html = renderToStaticMarkup(<SessionBoundary pathname={pathname} />);
        assert.match(html, /Sessione gestita dal backend/);
        assert.match(html, /Autorità verificata a ogni operazione/);
        assert.doesNotMatch(html, /non ancora collegate/);
    }
    const pending = renderToStaticMarkup(<SessionBoundary pathname="/onboarding" />);
    assert.match(pending, /sessione pendente consente solo lo stato della richiesta, non accesso aziendale/);
    assert.doesNotMatch(pending, /non ancora collegate|Autorità verificata/);
    for (const pathname of [null, "/", "/domains/catalog"]) {
        assert.match(renderToStaticMarkup(<SessionBoundary pathname={pathname} />), /Accesso non disponibile/);
    }
});
