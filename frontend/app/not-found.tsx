import React from "react";
import Link from "next/link";
export default function NotFound() {
    return (
        <>
            <h1>Pagina non trovata</h1>
            <p>L’area richiesta non esiste nella shell MVP.</p>
            <Link className="text-link" href="/">
                Torna alla panoramica
            </Link>
        </>
    );
}
