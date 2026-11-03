"use client";
import React, { useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "./ui/button";
import { domains } from "../lib/domains";

export function Shell({ children }: { children: ReactNode }) {
    const [open, setOpen] = useState(false);
    const trigger = useRef<HTMLButtonElement>(null);
    const pathname = usePathname();
    return (
        <div
            className="workspace"
            data-menu-open={open}
            onKeyDown={(event) => {
                if (event.key === "Escape" && open) {
                    setOpen(false);
                    trigger.current?.focus();
                }
            }}
        >
            <a className="skip-link" href="#main">
                Vai al contenuto
            </a>
            <header className="topbar">
                <Link
                    href="/"
                    className="brand"
                    aria-label="Enginia360 · Panoramica"
                >
                    <span className="brand-mark" aria-hidden="true">
                        E
                    </span>{" "}
                    Enginia360
                </Link>
                <span className="shell-label">
                    Ambiente di sviluppo · MVP-01
                </span>
                <Button
                    ref={trigger}
                    className="menu-trigger"
                    variant="outline"
                    aria-controls="domain-navigation"
                    aria-expanded={open}
                    onClick={() => setOpen(!open)}
                >
                    Menu domini
                </Button>
            </header>
            <aside className="sidebar" id="domain-navigation">
                <p className="eyebrow">Spazio di lavoro</p>
                <nav aria-label="Navigazione principale">
                    <Link
                        href="/"
                        aria-current={pathname === "/" ? "page" : undefined}
                        onClick={() => setOpen(false)}
                    >
                        Panoramica
                    </Link>
                    <p className="nav-section">Domini MVP</p>
                    {domains.map((domain, index) => (
                        <Link
                            key={domain.id}
                            href={`/domains/${domain.id}`}
                            aria-current={
                                pathname === `/domains/${domain.id}`
                                    ? "page"
                                    : undefined
                            }
                            onClick={() => setOpen(false)}
                        >
                            <span className="nav-index" aria-hidden="true">
                                {String(index + 1).padStart(2, "0")}
                            </span>
                            {domain.label}
                        </Link>
                    ))}
                </nav>
                <div className="context-note">
                    <strong>Nessun contesto aziendale attivo</strong>
                    <p>La shell non seleziona tenant, società o utente.</p>
                </div>
            </aside>
            <main id="main" tabIndex={-1} className="main-content">
                {children}
            </main>
            <footer>
                {pathname === "/organization" ? (
                    "Sessione gestita dal backend · Autorità verificata a ogni operazione; nessun permesso dal menu."
                ) : (
                    <>
                        Accesso non disponibile · Federazione e autorizzazioni
                        non ancora collegate.
                    </>
                )}
            </footer>
            <noscript>
                <style>
                    {
                        "@media(max-width:1023px){.sidebar{display:block!important}.menu-trigger{display:none!important}}"
                    }
                </style>
            </noscript>
        </div>
    );
}
