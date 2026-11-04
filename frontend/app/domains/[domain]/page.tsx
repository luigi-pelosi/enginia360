import React from "react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { domains } from "../../../lib/domains";
import { Badge } from "../../../components/ui/badge";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "../../../components/ui/card";
export default async function DomainPage({
    params,
}: {
    params: Promise<{ domain: string }>;
}) {
    const { domain: id } = await params;
    const domain = domains.find((candidate) => candidate.id === id);
    if (!domain) notFound();
    if (id === "document-types") redirect("/document-types");
    if (id === "catalog") redirect("/catalog");
    if (id === "counterparties") redirect("/counterparties");
    return (
        <>
            <div className="page-heading">
                <p className="eyebrow">Enginia360 / Domini MVP</p>
                <Badge variant="secondary">Non disponibile</Badge>
                <h1>{domain.label}</h1>
                <p className="lead">{domain.description}</p>
            </div>
            {id === "organization" && (
                <Card>
                    <CardHeader>
                        <h2>Amministrazione piattaforma</h2>
                    </CardHeader>
                    <CardContent>
                        <p>
                            Accesso federato e gestione della struttura per il
                            titolare dell’autorità globale verificata. Nessuna
                            delega o autorizzazione operativa implicita.
                        </p>
                        <Link
                            href="/organization"
                            prefetch={false}
                            className="text-link"
                        >
                            Apri amministrazione organizzativa
                        </Link>
                    </CardContent>
                </Card>
            )}
            {id === "identity" && (
                <Card>
                    <CardHeader><h2>Gestione utenti nel tenant</h2></CardHeader>
                    <CardContent>
                        <p>Delega distinta, ruoli e permessi configurabili per azioni supportate e assegnazione a utenti esistenti. Nessun invito o abilitazione implicita.</p>
                        <Link href="/users" prefetch={false} className="text-link">
                            Apri gestione utenti e ruoli
                        </Link>
                    </CardContent>
                </Card>
            )}
            <Card className="empty-state">
                <CardHeader>
                    <CardTitle>
                        <h2>Area non ancora implementata</h2>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {id === "organization" ? (
                        <p>
                            Deleghe nel tenant e gestione utenti: area non
                            ancora implementata. Il percorso piattaforma
                            disponibile sopra non concede accesso ai dati
                            operativi.
                        </p>
                    ) : (
                        <p>
                            Le funzioni operative di quest’area saranno
                            consegnate in {domain.milestone}. Non è possibile
                            leggere o modificare dati da questa shell.
                        </p>
                    )}
                    <p>
                        L’accesso federato e il contesto aziendale verificato
                        sono prerequisiti del futuro percorso operativo. La
                        presenza del collegamento nel menu non concede alcun
                        permesso.
                    </p>
                    <Link href="/" className="text-link">
                        Torna alla panoramica
                    </Link>
                </CardContent>
            </Card>
        </>
    );
}