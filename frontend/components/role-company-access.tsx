"use client";
import {useEffect, useRef, useState} from "react";
import {useTranslations} from "next-intl";
import {RefreshCw} from "lucide-react";
import {api, ApiError} from "@/lib/api";
import {can, type Row} from "@/lib/model";
import type {CompanyPartnerProps} from "@/components/business-partner-companies";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Checkbox} from "@/components/ui/checkbox";
import {Badge} from "@/components/ui/badge";
import {Alert, AlertDescription} from "@/components/ui/alert";
const canonical = (ids: string[]) => [...new Set(ids)].sort();
export function RoleCompanyAccess({roleId, session, scope, onError}: CompanyPartnerProps & {roleId: string}) {
  const t = useTranslations("partnerCompanies"), a = useTranslations("app");
  const readable = Boolean(roleId) && can(session, "roles", "read") && can(session, "companies", "read");
  const editable = readable && can(session, "roles", "assign_companies");
  const [options, setOptions] = useState<Row[]>([]), [initialIds, setInitialIds] = useState<string[]>([]), [ids, setIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [filter, setFilter] = useState(""), [revision, setRevision] = useState(0), [ready, setReady] = useState(false), [saved, setSaved] = useState(false);
  const locked = useRef(false), mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false;};}, []);
  useEffect(() => {
    if (!readable) return; let alive = true; const controller = new AbortController(); setLoading(true); setReady(false); setError(""); setSaved(false);
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
    Promise.all([companies(), api<{companyIds: string[]}>(scope(`/roles/${encodeURIComponent(roleId)}/companies`), "GET", undefined, {signal: controller.signal})])
      .then(([companies, data]) => {if (alive) {const selected = canonical(data.companyIds); setOptions(companies); setInitialIds(selected); setIds(selected); setReady(true);}})
      .catch(e => {if (alive) {setError(e instanceof ApiError ? onError(e) : t("referenceError")); setReady(false);}})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [readable, roleId, session, scope, onError, revision]);
  if (!readable) return null;
  const disabled = !editable || loading || busy || !ready;
  const changed = JSON.stringify(canonical(ids)) !== JSON.stringify(canonical(initialIds));
  const entries: Row[] = [...options, ...ids.filter(id => !options.some(company => company.id === id)).map(id => ({id, name: `${t("missingCompany")} · ${id}`}))];
  const visible = entries.filter(company => `${company.name ?? ""} ${company.code ?? ""}`.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
  async function save(event: {preventDefault: () => void; stopPropagation?: () => void}) {
    event.preventDefault(); event.stopPropagation?.();
    if (disabled || !changed || locked.current) return;
    locked.current = true; setBusy(true); setError(""); setSaved(false);
    const selected = canonical(ids); let accepted = false;
    try {
      await api(scope(`/roles/${encodeURIComponent(roleId)}/companies`), "PUT", {companyIds: selected});
      accepted = true;
      if (!mounted.current) return;
      setInitialIds(selected);
      const data = await api<{companyIds: string[]}>(scope(`/roles/${encodeURIComponent(roleId)}/companies`));
      if (mounted.current) {const current = canonical(data.companyIds); setInitialIds(current); setIds(current); setSaved(true);}
    } catch (e) {if (mounted.current) {setError(onError(e)); if (accepted || e instanceof ApiError && e.status === 0) setReady(false);}}
    finally {locked.current = false; if (mounted.current) setBusy(false);}
  }
  return <section data-role-company-access className="relations-section" aria-busy={loading || busy}>
    <div className="relation-heading"><h3>{t("authorizedCompanies")}</h3><div className="flex items-center gap-2"><Badge variant="secondary">{ids.length}</Badge><Button type="button" size="icon" variant="ghost" aria-label={a("refresh")} data-action="refresh-role-companies" disabled={loading || busy} onClick={() => {if (!locked.current) setRevision(value => value + 1);}}><RefreshCw size={16} /></Button></div></div>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {saved && <p role="status" className="success">{a("saved")}</p>}
    <Input aria-label={`${a("search")} ${t("authorizedCompanies")}`} value={filter} onChange={event => setFilter(event.target.value)} />
    <div className="relation-options">{loading ? <p>{a("loading")}</p> : visible.length ? visible.map(company => <Label key={company.id} className="relation-option"><Checkbox id={`role-company-${roleId}-${company.id}`} data-company-id={company.id} aria-label={`${company.name}${company.code ? ` · ${company.code}` : ""}`} checked={ids.includes(company.id)} disabled={disabled} onCheckedChange={checked => {if (!disabled && !locked.current) {setSaved(false); setIds(current => checked === true ? canonical([...current, company.id]) : current.filter(id => id !== company.id));}}} /><span><strong>{String(company.name)}</strong>{Boolean(company.code) && <small>{String(company.code)}</small>}</span>{company.is_enabled === false && <Badge variant="secondary">{a("disabled")}</Badge>}</Label>) : <p>{a("empty")}</p>}</div>
    {editable && <div className="flex flex-wrap justify-end gap-2"><Button type="button" variant="outline" data-action="cancel-role-companies" disabled={loading || busy || !changed} onClick={() => {if (!locked.current && ready) {setIds(initialIds); setError(""); setSaved(false);}}}>{a("cancel")}</Button><Button type="button" data-action="save-role-companies" disabled={disabled || !changed} onClick={save}>{t("saveCompanyAccess")}</Button></div>}
  </section>;
}
