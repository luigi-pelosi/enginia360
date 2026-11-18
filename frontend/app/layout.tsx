import type { Metadata } from "next";
import { cookies } from "next/headers";
import { NextIntlClientProvider } from "next-intl";
import it from "@/messages/it.json";
import en from "@/messages/en.json";
import "./globals.css";
export const metadata: Metadata = {
  title: "Enginia360",
  description: "Enginia360",
};
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = (await cookies()).get("locale")?.value === "en" ? "en" : "it";
  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider
          locale={locale}
          messages={locale === "en" ? en : it}
          timeZone="Europe/Rome"
        >
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
