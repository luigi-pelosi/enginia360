"use client";

import type {ReactNode} from "react";
import {useTranslations} from "next-intl";
import {ChevronRight} from "lucide-react";
import {Badge} from "@/components/ui/badge";
import {Checkbox} from "@/components/ui/checkbox";
import {groupPermissions, permissionMatches, permissionRows, type PermissionBranch, type Row} from "@/lib/model";
import it from "../messages/it.json";
import en from "../messages/en.json";

export function PermissionTree({rows, query = "", selectedIds, onSelectedIdsChange, disabled = false, renderLeaf}: {
  rows: Row[];
  query?: string;
  selectedIds?: string[];
  onSelectedIdsChange?: (ids: string[]) => void;
  disabled?: boolean;
  renderLeaf: (row: Row) => ReactNode;
}) {
  const t = useTranslations("app"), r = useTranslations("resources");
  const original = groupPermissions(rows);
  const allRows = original.flatMap(domain => domain.resources.flatMap(permissionRows));
  const originalBranches = new Map<string, PermissionBranch>();
  const index = (branch: PermissionBranch) => {originalBranches.set(branch.key, branch); branch.children.forEach(index);};
  original.forEach(domain => domain.resources.forEach(index));
  const tree = groupPermissions(rows.filter(row => permissionMatches(row, query, [it, en])));
  const searching = Boolean(query.trim());
  const selected = selectedIds ? new Set(selectedIds) : null;
  const count = (entries: Row[]) => <Badge variant="secondary" className="ml-auto shrink-0 tabular-nums"
    aria-label={selected ? t("selectedPermissions", {selected: entries.filter(row => selected.has(row.id)).length, total: entries.length}) : t("permissionCount", {count: entries.length})}>
    {selected ? `${entries.filter(row => selected.has(row.id)).length}/${entries.length}` : entries.length}
  </Badge>;
  const bulk = (entries: Row[], label: string, attributes: Record<string, string>) => {
    if (!selected) return null;
    const selectedCount = entries.filter(row => selected.has(row.id)).length;
    return <Checkbox {...attributes} aria-label={label} disabled={disabled || !onSelectedIdsChange || entries.length === 0}
      checked={selectedCount === 0 ? false : selectedCount === entries.length ? true : "indeterminate"}
      onClick={event => event.stopPropagation()}
      onKeyDown={event => {if (event.key === " " || event.key === "Enter") event.stopPropagation();}}
      onCheckedChange={checked => {
        if (disabled || !onSelectedIdsChange || !entries.length) return;
        const ids = new Set(entries.map(row => row.id));
        onSelectedIdsChange(checked === true ? [...new Set([...selected, ...ids])] : [...selected].filter(id => !ids.has(id)));
      }} />;
  };
  const renderBranch = (branch: PermissionBranch): ReactNode => {
    const branchRows = permissionRows(originalBranches.get(branch.key)!);
    const label = branch.key === "settings-system" ? t("system") : branch.key === "settings-master-data" ? t("masterData") : branch.key === "settings-business-partners" ? r("business-partners") : r.has(branch.key) ? r(branch.key) : branch.key;
    return <details key={`${query}-${branch.key}`} open={searching || undefined} data-permission-resource={branch.key} className="rounded-md [&[open]>summary>svg]:rotate-90">
      <summary aria-label={label} className="flex cursor-pointer list-none items-center gap-2 rounded-md px-3 py-2 text-sm font-medium outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <ChevronRight aria-hidden="true" className="size-4 shrink-0 transition-transform" />
        {bulk(branchRows, `${t("selectAll")} · ${label}`, {"data-permission-resource-checkbox": branch.key})}
        <span>{label}</span>{count(selected ? branchRows : permissionRows(branch))}
      </summary>
      {branch.rows.length > 0 && <ul className="ml-4 divide-y border-l pl-2 sm:ml-5 sm:pl-4">
        {branch.rows.map(row => <li key={row.id} data-permission-code={String(row.code ?? "")}>{renderLeaf(row)}</li>)}
      </ul>}
      {branch.children.length > 0 && <div className="ml-3 space-y-1 border-l pl-2 sm:ml-5 sm:pl-3">{branch.children.map(renderBranch)}</div>}
    </details>;
  };
  return <div className="space-y-2">
    {selected && <div className="flex items-center gap-2 rounded-md border px-4 py-3 text-sm font-medium">
      {bulk(allRows, t("selectAll"), {"data-permission-selection": "all"})}
      <span>{t("selectAll")}</span>{count(allRows)}
    </div>}
    {!tree.length ? <p className="p-4 text-sm text-muted-foreground">{t("empty")}</p> : <div className="divide-y rounded-md border">
      {tree.map(domain => {
        const originalDomain = original.find(entry => entry.key === domain.key)!;
        const domainRows = originalDomain.resources.flatMap(permissionRows);
        const domainLabel = t(domain.key === "other" ? "otherPermissions" : domain.key);
        return <details key={`${query}-${domain.key}`} open={searching || undefined} data-permission-domain={domain.key} className="group/domain">
          <summary aria-label={domainLabel} className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-semibold outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
            <ChevronRight aria-hidden="true" className="size-4 shrink-0 transition-transform group-open/domain:rotate-90" />
            {bulk(domainRows, `${t("selectAll")} · ${domainLabel}`, {"data-permission-domain-checkbox": domain.key})}
            <span>{domainLabel}</span>{count(selected ? domainRows : domain.resources.flatMap(permissionRows))}
          </summary>
          <div className="space-y-1 border-t p-2 sm:pl-6">
            {domain.resources.map(renderBranch)}
          </div>
        </details>;
      })}
    </div>}
  </div>;
}
