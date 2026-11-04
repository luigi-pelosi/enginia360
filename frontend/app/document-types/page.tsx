import React from "react";
import { cookies } from "next/headers";
import { privateRead } from "../../lib/private-backend";
import { documentTypesReadPath, finiteDocumentTypesRead, type DocumentTypesQuery } from "../../lib/document-types";
import { DocumentTypesWorkspace } from "../../components/document-types-workspace";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export default async function DocumentTypesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const raw = await searchParams;
  // Do not normalize duplicate or unknown query keys away before validating.
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (Array.isArray(value)) for (const item of value) params.append(key, item);
    else if (value !== undefined) params.append(key, value);
  }
  const path = "/api/v1/document-types" + (params.size ? "?" + params.toString() : "");
  if (!finiteDocumentTypesRead(path)) return <DocumentTypesWorkspace initial={{ status: 400, data: null, query: {} }} />;
  const query = raw as DocumentTypesQuery;
  const cookie = (await cookies()).toString();
  const session = await privateRead("/auth/session", cookie);
  if (session.status !== 200 || !session.value?.authenticated) return <DocumentTypesWorkspace initial={{ status: session.status === 200 ? 401 : session.status, data: null, query: {} }} />;
  const result = await privateRead(documentTypesReadPath(query), cookie);
  return <DocumentTypesWorkspace initial={{ status: result.status, data: result.value, query }} />;
}
