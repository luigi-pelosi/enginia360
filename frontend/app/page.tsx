import React from "react";
import Link from "next/link";
import { domains } from "../lib/domains";
import { Badge } from "../components/ui/badge";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "../components/ui/card";
export default function Home() {
    return (
        <>
            <div className="page-heading">
                <p className="eyebrow">Enginia360 / Panoramica</p>
                <Badge variant="outline">MVP in sviluppo</Badge>
                <h1>Uno spazio per il tuo lavoro.</h1>
                <p className="lead">
                    Sette domini, un unico percorso gestionale. Il nuovo MVP è
                    in costruzione.
                </p>
            </div>
            <section className="boundary" aria-labelledby="boundary-title">
                <span className="status-dot" aria-hidden="true" />
                <div>
                    <h2 id="boundary-title">
                        Navigazione disponibile. Ogni area verifica
                        accesso e autorizzazioni.
                    </h2>
                    <p>
                        Questa panoramica non carica dati aziendali né seleziona
                        un contesto. Apri un percorso collegato per verificare
                        sessione e permessi correnti; il menu non concede accesso.
                    </p>
                </div>
            </section>
            <div className="section-heading">
                <h2>Domini del nuovo MVP</h2>
                <span>Perimetro approvato · D96</span>
            </div>
            <div className="domain-grid">
                {domains.map((domain, index) => (
                    <Card key={domain.id}>
                        <CardHeader>
                            <div className="card-topline">
                                <span className="domain-number">
                                    0{index + 1}
                                </span>
                                <Badge variant="secondary">
                                    Verifica accesso
                                </Badge>
                            </div>
                            <CardTitle>
                                <Link href={`/domains/${domain.id}`}>
                                    {domain.label}
                                    <span aria-hidden="true"> ↗</span>
                                </Link>
                            </CardTitle>
                            <CardDescription>
                                {domain.description}
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <p className="milestone">
                                Ambito · {domain.milestone}
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>
            <p className="scope-note">
                Questa shell non sostituisce ancora le schermate storiche e non
                dimostra il completamento dei domini. Nessuna integrazione ERP è
                richiesta o invocata.
            </p>
        </>
    );
}
