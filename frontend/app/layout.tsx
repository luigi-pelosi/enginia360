import React from "react";
import type { Metadata } from "next";
import { Shell } from "../components/shell";
import "./globals.css";
export const metadata: Metadata = {
    title: {
        default: "Enginia360 · Spazio di lavoro",
        template: "%s · Enginia360",
    },
    description:
        "Shell tecnica del nuovo MVP Enginia360. Funzioni operative non ancora disponibili.",
    robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";
export default function RootLayout({
    children,
}: Readonly<{ children: React.ReactNode }>) {
    return (
        <html lang="it">
            <body>
                <Shell>{children}</Shell>
            </body>
        </html>
    );
}
