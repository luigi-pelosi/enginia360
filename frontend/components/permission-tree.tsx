"use client";

import type {ReactNode} from "react";
import {useTranslations} from "next-intl";
import {ChevronRight} from "lucide-react";
import {Badge} from "@/components/ui/badge";
import {Checkbox} from "@/components/ui/checkbox";
import {groupPermissions, permissionMatches, type Row} from "@/lib/model";
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
  const allRows = original.flatMap(domain => domain.resources.flatMap(resource => resource.rows));
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
  return <div className="space-y-2">
    {selected && <div className="flex items-center gap-2 rounded-md border px-4 py-3 text-sm font-medium">
      {bulk(allRows, t("selectAll"), {"data-permission-selection": "all"})}
      <span>{t("selectAll")}</span>{count(allRows)}
    </div>}
    {!tree.length ? <p className="p-4 text-sm text-muted-foreground">{t("empty")}</p> : <div className="divide-y rounded-md border">
      {tree.map(domain => {
        const originalDomain = original.find(entry => entry.key === domain.key)!;
        const domainRows = originalDomain.resources.flatMap(resource => resource.rows);
        const domainLabel = t(domain.key === "other" ? "otherPermissions" : domain.key);
        return <details key={`${query}-${domain.key}`} open={searching || undefined} data-permission-domain={domain.key} className="group/domain">
          <summary aria-label={domainLabel} className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-semibold outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
            <ChevronRight aria-hidden="true" className="size-4 shrink-0 transition-transform group-open/domain:rotate-90" />
            {bulk(domainRows, `${t("selectAll")} · ${domainLabel}`, {"data-permission-domain-checkbox": domain.key})}
            <span>{domainLabel}</span>{count(selected ? domainRows : domain.resources.flatMap(resource => resource.rows))}
          </summary>
          <div className="space-y-1 border-t p-2 sm:pl-6">
            {domain.resources.map(resource => {
              const resourceRows = originalDomain.resources.find(entry => entry.key === resource.key)!.rows;
              const resourceLabel = r.has(resource.key) ? r(resource.key) : resource.key;
              return <details key={`${query}-${resource.key}`} open={searching || undefined} data-permission-resource={resource.key} className="group/resource rounded-md">
                <summary aria-label={resourceLabel} className="flex cursor-pointer list-none items-center gap-2 rounded-md px-3 py-2 text-sm font-medium outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
                  <ChevronRight aria-hidden="true" className="size-4 shrink-0 transition-transform group-open/resource:rotate-90" />
                  {bulk(resourceRows, `${t("selectAll")} · ${resourceLabel}`, {"data-permission-resource-checkbox": resource.key})}
                  <span>{resourceLabel}</span>{count(selected ? resourceRows : resource.rows)}
                </summary>
                <ul className="ml-4 divide-y border-l pl-2 sm:ml-5 sm:pl-4">
                  {resource.rows.map(row => <li key={row.id} data-permission-code={String(row.code ?? "")}>{renderLeaf(row)}</li>)}
                </ul>
              </details>;
            })}
          </div>
        </details>;
      })}
    </div>}
  </div>;
}
