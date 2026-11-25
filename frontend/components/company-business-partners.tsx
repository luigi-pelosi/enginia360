"use client";
import {useEffect, useState} from "react";
import {useTranslations} from "next-intl";
import {Eye, RefreshCw} from "lucide-react";
import {api} from "@/lib/api";
import {Button} from "@/components/ui/button";
import {FilterBar} from "@/components/ui/filter-bar";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Checkbox} from "@/components/ui/checkbox";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Card} from "@/components/ui/card";
import {Badge} from "@/components/ui/badge";
import {Alert, AlertDescription} from "@/components/ui/alert";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {companyPartnerReadable, companyPartnerActionsClass, type CompanyOption, type CompanyPartner, type CompanyPartnerProps} from "@/components/business-partner-companies";
type Result = {items: CompanyPartner[]; total: number; page: number; pageSize: number};
export function CompanyBusinessPartners({session, scope, onError, onOpenPartner, recoveryKey}: CompanyPartnerProps & {onOpenPartner: (id: string) => void; recoveryKey?: string | null}) {
  const t = useTranslations("partnerCompanies"), a = useTranslations("app"), bp = useTranslations("businessPartners");
  const readable = companyPartnerReadable(session);
  const [options, setOptions] = useState<CompanyOption[]>([]), [companyId, setCompanyId] = useState("");
  const [result, setResult] = useState<Result>({items: [], total: 0, page: 1, pageSize: 25}), [error, setError] = useState("");
  const [role, setRole] = useState(""), [usableOnly, setUsableOnly] = useState(false), [search, setSearch] = useState(""), [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false), [optionsLoading, setOptionsLoading] = useState(true), [optionsError, setOptionsError] = useState(""), [revision, setRevision] = useState(0);
  const [restoredKey, setRestoredKey] = useState<string | null | undefined>(undefined);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  useEffect(() => {
    let saved;
    try {saved = recoveryKey ? JSON.parse(sessionStorage.getItem(recoveryKey) || "null")?.companyFilters : null;} catch {saved = null;}
    if (saved?.version !== 2) saved = null;
    setCompanyId(typeof saved?.companyId === "string" ? saved.companyId : "");
    setRole(["CUSTOMER", "SUPPLIER"].includes(saved?.role) ? saved.role : "");
    setUsableOnly(saved?.usableOnly === true);
    setSearch(typeof saved?.search === "string" ? saved.search.slice(0, 200) : "");
    setPage(Number.isSafeInteger(saved?.page) && saved.page > 0 ? saved.page : 1);
    setFiltersExpanded(saved?.filtersExpanded === true);
    setRestoredKey(recoveryKey ?? null);
  }, [recoveryKey]);
  useEffect(() => {
    if (!recoveryKey || restoredKey !== recoveryKey || optionsLoading) return;
    try {const stored = JSON.parse(sessionStorage.getItem(recoveryKey) || "null"); sessionStorage.setItem(recoveryKey, JSON.stringify({...stored, companyFilters: {version: 2, companyId, role, usableOnly, search, page, filtersExpanded}}));} catch { /* Il recupero è facoltativo. */ }
  }, [recoveryKey, restoredKey, optionsLoading, companyId, role, usableOnly, search, page, filtersExpanded]);
  useEffect(() => {
    if (!readable) return; let alive = true; const controller = new AbortController(); setOptionsLoading(true); setOptionsError("");
    api<{items: CompanyOption[]}>(scope("/business-partner-companies/options"), "GET", undefined, {signal: controller.signal}).then(data => {if (alive) {const entries = data.items.filter(company => company.permissions.includes("read")); setOptions(entries); setCompanyId(current => entries.some(company => company.id === current) ? current : "");}}).catch(e => {if (alive) {setOptions([]); setCompanyId(""); setOptionsError(onError(e));}}).finally(() => {if (alive) setOptionsLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [readable, session, scope, onError, revision]);
  const selectedReadable = readable && (!companyId || options.some(company => company.id === companyId && company.permissions.includes("read")));
  useEffect(() => {
    if (!selectedReadable || optionsLoading || optionsError) {setResult({items: [], total: 0, page, pageSize: 25}); return;}
    let alive = true; const controller = new AbortController(); setLoading(true); setError(""); setResult({items: [], total: 0, page, pageSize: 25});
    const endpoint = companyId ? `/companies/${encodeURIComponent(companyId)}/business-partners` : "/business-partner-companies";
    api<Result>(scope(`${endpoint}?role=${role}&usableOnly=${usableOnly}&search=${encodeURIComponent(search)}&page=${page}&pageSize=25`), "GET", undefined, {signal: controller.signal})
      .then(data => {if (alive) {setResult(data); if (!data.items.length && page > 1) setPage(Math.max(1, Math.ceil(data.total / 25)));}})
      .catch(e => {if (alive) setError(onError(e));}).finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [selectedReadable, companyId, role, usableOnly, search, page, revision, optionsLoading, optionsError, scope, onError]);
  if (!readable) return null;
  return <Card data-company-partners className="gap-0 overflow-hidden py-0">
    <FilterBar id="company-partner-filters" expanded={filtersExpanded} onExpandedChange={setFiltersExpanded} fields={[
      {key: "search", minWidth: 224, grow: true, content: (<div className="space-y-2"><Label htmlFor="company-partner-search">{a("search")}</Label><Input id="company-partner-search" value={search} maxLength={200} onChange={event => {setSearch(event.target.value); setPage(1);}} /></div>)},
      {key: "company", minWidth: 200, content: (<div className="space-y-2"><Label htmlFor="company-partner-company">{t("company")}</Label><Select value={companyId || "all"} disabled={optionsLoading || Boolean(optionsError)} onValueChange={value => {if (!optionsLoading && (value === "all" || options.some(company => company.id === value && company.permissions.includes("read")))) {setCompanyId(value === "all" ? "" : value); setPage(1);}}}><SelectTrigger id="company-partner-company" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">{t("allCompanies")}</SelectItem>{options.map(company => <SelectItem key={company.id} value={company.id}>{company.name}{company.code ? ` · ${company.code}` : ""}{!company.is_enabled ? ` · ${a("disabled")}` : ""}</SelectItem>)}</SelectContent></Select></div>)},
      {key: "role", minWidth: 160, content: (<div className="space-y-2"><Label htmlFor="company-partner-role">{t("role")}</Label><Select value={role || "all"} onValueChange={value => {if (["all", "CUSTOMER", "SUPPLIER"].includes(value)) {setRole(value === "all" ? "" : value); setPage(1);}}}><SelectTrigger id="company-partner-role" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">{t("allRoles")}</SelectItem>{["CUSTOMER", "SUPPLIER"].map(value => <SelectItem key={value} value={value}>{t(value)}</SelectItem>)}</SelectContent></Select></div>)},
      {key: "usable", minWidth: 220, content: (<div className="flex items-center justify-between gap-3"><Label className="flex items-center gap-2"><Checkbox id="company-partner-usable" checked={usableOnly} onCheckedChange={checked => {setUsableOnly(checked === true); setPage(1);}} />{t("usableOnly")}</Label><Button type="button" size="icon" variant="ghost" data-action="refresh-company-partners" aria-label={a("refresh")} disabled={loading || optionsLoading} onClick={() => setRevision(value => value + 1)}><RefreshCw size={16} /></Button></div>)},
    ]} />
    {(error || optionsError) && <Alert variant="destructive"><AlertDescription>{error || optionsError}</AlertDescription></Alert>}
    <div className="table-scroll" aria-busy={loading || optionsLoading}><Table><TableHeader><TableRow><TableHead kind="text">{t("company")}</TableHead><TableHead kind="text">{bp("code")}</TableHead><TableHead kind="text">{t("partner")}</TableHead><TableHead kind="status">{t("partnerStatus")}</TableHead><TableHead kind="status">{t("relationshipStatus")}</TableHead><TableHead kind="status">{t("assignedRoles")}</TableHead><TableHead kind="text">{t("usableRoles")}</TableHead><TableHead kind="actions" className={companyPartnerActionsClass}>{a("actions")}</TableHead></TableRow></TableHeader><TableBody>
      {!result.items.length && <TableRow><TableCell colSpan={8}><p role="status" className="table-empty">{a(loading || optionsLoading ? "loading" : "empty")}</p></TableCell></TableRow>}
      {result.items.map(row => <TableRow key={row.id} data-company-id={row.company_id} data-business-partner-id={row.business_partner_id}><TableCell kind="text" className="min-w-40 whitespace-normal">{row.company_name}</TableCell><TableCell kind="text">{row.bp_code || "—"}</TableCell><TableCell kind="text" className="min-w-48 whitespace-normal">{row.bp_name}</TableCell><TableCell kind="status"><Badge variant="secondary">{row.bp_status ? bp(row.bp_status) : "—"}</Badge></TableCell><TableCell kind="status"><Badge variant="secondary">{t(row.status)}</Badge></TableCell><TableCell kind="status" className="whitespace-normal">{row.roles.length ? <div className="flex flex-wrap items-center gap-x-3 gap-y-1">{row.roles.map(assigned => <span key={assigned.id} className="inline-flex items-center gap-1"><span>{t(assigned.role_code)}</span><Badge variant="secondary">{t(assigned.status)}</Badge></span>)}</div> : "—"}</TableCell><TableCell kind="text" data-usable-roles={row.business_partner_id}>{row.usable_roles.map(usable => t(usable)).join(", ") || "—"}</TableCell><TableCell kind="actions" className={companyPartnerActionsClass}><Button type="button" variant="ghost" size="icon" className="size-8" data-action={`open-company-partner-${row.business_partner_id}`} aria-label={`${a("details")} ${row.bp_name}`} title={a("details")} disabled={loading} onClick={() => {if (!loading && selectedReadable) onOpenPartner(row.business_partner_id);}}><Eye size={16} aria-hidden /></Button></TableCell></TableRow>)}
    </TableBody></Table></div>
    <div className="pagination"><span>{result.total} {a("records", {count: result.total})} · {a("page")} {page} {a("of")} {Math.max(1, Math.ceil(result.total / 25))}</span><div><Button type="button" variant="outline" data-action="previous-company-partners" disabled={loading || page <= 1} onClick={() => {if (!loading && page > 1) setPage(value => value - 1);}}>{a("previous")}</Button><Button type="button" variant="outline" data-action="next-company-partners" disabled={loading || page * 25 >= result.total} onClick={() => {if (!loading && page * 25 < result.total) setPage(value => value + 1);}}>{a("next")}</Button></div></div>
  </Card>;
}
