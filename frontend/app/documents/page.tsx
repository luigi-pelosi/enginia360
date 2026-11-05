import React from "react";
import { cookies } from "next/headers";
import { privateRead } from "../../lib/private-backend";
import { documentsReadPath, finiteDocumentsRead, type DocumentsQuery } from "../../lib/documents";
import { DocumentsWorkspace } from "../../components/documents-workspace";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export default async function DocumentsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
 const raw = await searchParams; const params = new URLSearchParams();
 for (const [key,value] of Object.entries(raw)) {
  if (Array.isArray(value)) for (const item of value) params.append(key,item);
  else if (value !== undefined) params.append(key,value);
 }
 const path = "/api/v1/documents" + (params.size ? "?" + params.toString() : "");
 if (!finiteDocumentsRead(path)) return <DocumentsWorkspace initial={{status:400,data:null,query:{}}} />;
 const query = raw as DocumentsQuery; const cookie = (await cookies()).toString();
 const session = await privateRead("/auth/session",cookie);
 if (session.status !== 200 || !session.value?.authenticated) return <DocumentsWorkspace initial={{status:session.status === 200 ? 401 : session.status,data:null,query:{}}} />;
 const result = await privateRead(documentsReadPath(query),cookie);
 return <DocumentsWorkspace initial={{status:result.status,data:result.value,query}} />;
}
