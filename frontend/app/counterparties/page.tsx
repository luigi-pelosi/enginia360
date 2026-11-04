import React from "react";
import { cookies } from "next/headers";
import { privateRead } from "../../lib/private-backend";
import { counterpartyReadPath, finiteCounterpartyRead, type CounterpartyQuery } from "../../lib/counterparties";
import { CounterpartyWorkspace } from "../../components/counterparty-workspace";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export default async function CounterpartiesPage({ searchParams }: { searchParams: Promise<CounterpartyQuery> }) {
  const query = await searchParams;
  const path = counterpartyReadPath(query);
  if (!finiteCounterpartyRead(path)) return <CounterpartyWorkspace initial={{ status: 400, data: null, query: {} }} />;
  const cookie = (await cookies()).toString();
  const session = await privateRead("/auth/session", cookie);
  if (session.status !== 200 || !session.value?.authenticated) return <CounterpartyWorkspace initial={{ status: session.status === 200 ? 401 : session.status, data: null, query: {} }} />;
  const result = await privateRead(path, cookie);
  return <CounterpartyWorkspace initial={{ status: result.status, data: result.value, query }} />;
}
