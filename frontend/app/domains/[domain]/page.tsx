import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
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
    return (
        <>
            <div className="page-heading">
                <p className="eyebrow">Enginia360 / Domini MVP</p>
                <Badge variant="secondary">Non disponibile</Badge>
                <h1>{domain.label}</h1>
                <p className="lead">{domain.description}</p>
            </div>
            <Card className="empty-state">
                <CardHeader>
                    <CardTitle>
                        <h2>Area non ancora implementata</h2>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p>
                        Le funzioni operative di quest’area saranno consegnate
                        in {domain.milestone}. Non è possibile leggere o
                        modificare dati da questa shell.
                    </p>
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
