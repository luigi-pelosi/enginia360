"use client";
import {useState} from "react";
import {useTranslations} from "next-intl";
import {Button} from "@/components/ui/button";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Checkbox} from "@/components/ui/checkbox";
import {Label} from "@/components/ui/label";
import {Badge} from "@/components/ui/badge";
import {rowLabel, type Row} from "@/lib/model";

export type CoverageEntry = {companyId: string; siteScope: "all_sites" | "selected_sites" | ""; siteIds: string[]};
export type CoverageDraft = {companies: Row[]; sites: Row[]; initial: CoverageEntry[]; coverage: CoverageEntry[]};
export function coverageChanged(draft: CoverageDraft) {
  const canonical = (entries: CoverageEntry[]) => JSON.stringify(entries.map(entry => ({...entry, siteIds: [...entry.siteIds].sort()})).sort((a,b) => a.companyId.localeCompare(b.companyId)));
  return canonical(draft.initial) !== canonical(draft.coverage);
}
export function coverageValid(draft: CoverageDraft) {
  const entries = draft.coverage;
  return entries.length <= 500 && new Set(entries.map(e => e.companyId)).size === entries.length &&
    entries.reduce((n,e) => n + e.siteIds.length, 0) <= 500 && entries.every(entry => entry.companyId &&
      (entry.siteScope === "all_sites" ? entry.siteIds.length === 0 : entry.siteScope === "selected_sites" && entry.siteIds.length > 0) &&
      new Set(entry.siteIds).size === entry.siteIds.length && entry.siteIds.every(id => id && !draft.sites.some(site => site.id === id && site.company_id !== entry.companyId)));
}
export function PurchasingCoverageEditor({draft, editable, loading, busy, onChange}: {
  draft?: CoverageDraft; editable: boolean; loading: boolean; busy: boolean; onChange: (coverage: CoverageEntry[]) => void;
}) {
  const t = useTranslations("app"), f = useTranslations("fields");
  const [companyId, setCompanyId] = useState("");
  const disabled = !editable || loading || busy || !draft;
  const change = (entries: CoverageEntry[]) => {if (!disabled) onChange(entries);};
  const available = draft?.companies.filter(company => !draft.coverage.some(entry => entry.companyId === company.id)) ?? [];
  const label = (row: Row) => `${rowLabel(row)}${row.is_enabled === false ? ` · ${t("disabled")}` : ""}`;
  return <section data-purchasing-coverage className="relations-section" aria-busy={loading}>
    <div className="relation-heading"><h3>{t("purchasingCoverage")}</h3><Badge variant="secondary">{draft?.coverage.length ?? 0}</Badge></div>
    {loading || !draft ? <p role="status">{t("loading")}</p> : <div className="grid gap-3">
      <div className="flex gap-2">
        <Select value={companyId} disabled={disabled || !available.length} onValueChange={value => {if (!disabled) setCompanyId(value)}}>
          <SelectTrigger aria-label={f("company_id")} className="min-w-0 flex-1"><SelectValue placeholder={f("company_id")} /></SelectTrigger>
          <SelectContent>{available.map(company => <SelectItem key={company.id} value={company.id}>{label(company)}</SelectItem>)}</SelectContent>
        </Select>
        <Button type="button" variant="outline" disabled={disabled || !available.some(company => company.id === companyId)} onClick={() => {
          if (disabled || !available.some(company => company.id === companyId)) return;
          change([...draft.coverage, {companyId, siteScope: "", siteIds: []}]); setCompanyId("");
        }}>{t("add")}</Button>
      </div>
      {draft.coverage.map(entry => {
        const company = draft.companies.find(row => row.id === entry.companyId);
        const sites = draft.sites.filter(site => site.company_id === entry.companyId);
        const missing = entry.siteIds.filter(id => !draft.sites.some(site => site.id === id)).map(id => ({id}));
        return <div key={entry.companyId} data-coverage-company={entry.companyId} className="grid gap-3 rounded-md border p-3">
          <div className="flex items-center justify-between gap-2"><strong className="text-sm">{company ? label(company) : entry.companyId}</strong>
            <Button type="button" variant="ghost" size="sm" disabled={disabled} aria-label={`${t("remove")} ${company ? rowLabel(company) : entry.companyId}`} onClick={() => change(draft.coverage.filter(row => row.companyId !== entry.companyId))}>{t("remove")}</Button>
          </div>
          <Select value={entry.siteScope} disabled={disabled} onValueChange={mode => {
            if (mode !== "all_sites" && mode !== "selected_sites") return;
            change(draft.coverage.map(row => row.companyId === entry.companyId ? {...row, siteScope: mode, siteIds: mode === "all_sites" ? [] : row.siteIds} : row));
          }}>
            <SelectTrigger data-coverage-mode={entry.companyId} aria-label={t("siteScope")} className="w-full"><SelectValue placeholder={t("selectSiteScope")} /></SelectTrigger>
            <SelectContent><SelectItem value="all_sites">{t("allSites")}</SelectItem><SelectItem value="selected_sites">{t("selectedSites")}</SelectItem></SelectContent>
          </Select>
          {entry.siteScope === "selected_sites" && <div className="grid gap-2">
            {[...sites, ...missing].map(site => <Label key={site.id} className="relation-option">
              <Checkbox data-coverage-site={site.id} aria-label={label(site)} checked={entry.siteIds.includes(site.id)} disabled={disabled} onCheckedChange={checked => {
                change(draft.coverage.map(row => row.companyId === entry.companyId ? {...row, siteIds: checked === true ? [...new Set([...row.siteIds, site.id])] : row.siteIds.filter(id => id !== site.id)} : row));
              }} /><span>{label(site)}</span>
            </Label>)}
            {!entry.siteIds.length && <p className="text-sm text-destructive" role="alert">{t("selectAtLeastOneSite")}</p>}
          </div>}
        </div>;
      })}
      {!draft.coverage.length && <p className="text-sm text-muted-foreground">{t("empty")}</p>}
    </div>}
  </section>;
}
