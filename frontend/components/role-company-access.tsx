"use client";
import {useEffect, useState} from "react";
import {useTranslations} from "next-intl";
import {RefreshCw} from "lucide-react";
import {api, ApiError} from "@/lib/api";
import type {Row} from "@/lib/model";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Checkbox} from "@/components/ui/checkbox";
import {Badge} from "@/components/ui/badge";
import {Alert, AlertDescription} from "@/components/ui/alert";
export function RoleCompanyAccess({roleId, scope, onError, ids, ready, error, editable, busy, onIdsChange, onLookupState}: {
  roleId: string; scope: (path: string) => string; onError: (error: unknown) => string;
  ids: string[]; ready: boolean; error: string; editable: boolean; busy: boolean;
  onIdsChange: (ids: string[]) => void; onLookupState: (ready: boolean, error: string) => void;
}) {
  const t = useTranslations("partnerCompanies"), a = useTranslations("app");
  const [options, setOptions] = useState<Row[]>([]), [loading, setLoading] = useState(true), [lookupError, setLookupError] = useState("");
  const [filter, setFilter] = useState(""), [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true; const controller = new AbortController(); setLoading(true); setLookupError(""); onLookupState(false, "");
    async function companies() {
      const all = new Map<string, Row>(); let page = 1;
      for (;;) {
        const data = await api<{items: Row[]; total: number; page: number; pageSize: number}>(scope(`/data/companies?page=${page}&pageSize=100`), "GET", undefined, {signal: controller.signal});
        if (!Array.isArray(data.items) || !Number.isSafeInteger(data.total) || data.total < 0 || data.page !== page) throw new Error(t("referenceError"));
        const before = all.size;
        for (const company of data.items) all.set(company.id, company);
        if (all.size === data.total) return [...all.values()];
        if (all.size > data.total || all.size === before || data.items.length === 0) throw new Error(t("referenceError"));
        page++;
      }
    }
    companies().then(companies => {if (alive) {setOptions(companies); onLookupState(true, "");}})
      .catch(e => {if (alive) {const message = e instanceof ApiError ? onError(e) : t("referenceError"); setLookupError(message); onLookupState(false, message);}})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [scope, onError, onLookupState, revision]);
  const disabled = !editable || loading || busy || !ready || !!error || !!lookupError;
  const entries: Row[] = [...options, ...ids.filter(id => !options.some(company => company.id === id)).map(id => ({id, name: `${t("missingCompany")} · ${id}`}))];
  const visible = entries.filter(company => `${company.name ?? ""} ${company.code ?? ""}`.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
  return <section data-role-company-access className="relations-section" aria-busy={loading || !ready || busy}>
    <div className="relation-heading"><h3>{t("authorizedCompanies")}</h3><div className="flex items-center gap-2"><Badge variant="secondary">{ids.length}</Badge><Button type="button" size="icon" variant="ghost" aria-label={a("refresh")} data-action="refresh-role-companies" disabled={loading || busy} onClick={() => {if (!loading && !busy) setRevision(value => value + 1);}}><RefreshCw size={16} /></Button></div></div>
    {(error || lookupError) && <Alert variant="destructive"><AlertDescription>{error || lookupError}</AlertDescription></Alert>}
    <Input aria-label={`${a("search")} ${t("authorizedCompanies")}`} value={filter} onChange={event => setFilter(event.target.value)} />
    {loading && <p>{a("loading")}</p>}
    <div className="relation-options">{visible.length ? visible.map(company => <Label key={company.id} className="relation-option"><Checkbox id={`role-company-${roleId || "new"}-${company.id}`} data-company-id={company.id} aria-label={`${company.name}${company.code ? ` · ${company.code}` : ""}`} checked={ids.includes(company.id)} disabled={disabled} onCheckedChange={checked => {if (!disabled) onIdsChange(checked === true ? [...new Set([...ids, company.id])].sort() : ids.filter(id => id !== company.id));}} /><span><strong>{String(company.name)}</strong>{Boolean(company.code) && <small>{String(company.code)}</small>}</span>{company.is_enabled === false && <Badge variant="secondary">{a("disabled")}</Badge>}</Label>) : !loading && <p>{a("empty")}</p>}</div>
  </section>;
}
