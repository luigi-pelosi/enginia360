"use client";
import {useEffect, useRef, useState} from "react";
import {useTranslations} from "next-intl";
import {Plus, Pencil, Ban, Check, RefreshCw} from "lucide-react";
import {api, ApiError} from "@/lib/api";
import {can, type Session} from "@/lib/model";
import {Button} from "@/components/ui/button";
import {Label} from "@/components/ui/label";
import {Checkbox} from "@/components/ui/checkbox";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Card} from "@/components/ui/card";
import {Badge} from "@/components/ui/badge";
import {Alert, AlertDescription} from "@/components/ui/alert";
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter} from "@/components/ui/dialog";
import {AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction} from "@/components/ui/alert-dialog";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
export type CompanyOption = {id: string; name: string; code: string | null; is_enabled: boolean; permissions: string[]};
export type PartnerRoleCode = "CUSTOMER" | "SUPPLIER";
export type CompanyPartner = {id: string; company_id: string; business_partner_id: string; company_name: string; status: "ACTIVE" | "BLOCKED"; version: number; roles: {id: string; role_code: PartnerRoleCode; status: "ACTIVE" | "BLOCKED"}[]; usable_roles: PartnerRoleCode[]; bp_code?: string; bp_name?: string; bp_status?: string};
export type CompanyPartnerProps = {session: Session; scope: (path: string) => string; onError: (error: unknown) => string};
export const companyPartnerReadable = (session: Session) => can(session, "business-partners", "read") && can(session, "business-partner-companies", "read");
export const companyPartnerActionsClass = "w-[120px] min-w-[120px] max-w-[120px] text-right";
const roleCodes: PartnerRoleCode[] = ["CUSTOMER", "SUPPLIER"];
type Operation = {companyId: string; role?: PartnerRoleCode; status: "ACTIVE" | "BLOCKED"; version: number};
export function BusinessPartnerCompanies({businessPartnerId, session, scope, onError}: CompanyPartnerProps & {businessPartnerId: string}) {
  const t = useTranslations("partnerCompanies"), a = useTranslations("app");
  const readable = companyPartnerReadable(session);
  const [items, setItems] = useState<CompanyPartner[]>([]), [options, setOptions] = useState<CompanyOption[]>([]);
  const [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [revision, setRevision] = useState(0), [busy, setBusy] = useState(false);
  const [association, setAssociation] = useState<{companyId: string; roles: PartnerRoleCode[]} | null>(null);
  const [managedCompany, setManagedCompany] = useState<string | null>(null), [operation, setOperation] = useState<Operation | null>(null);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const locked = useRef(false), mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false;};}, []);
  useEffect(() => {
    if (!businessPartnerId || !readable) return;
    let alive = true; const controller = new AbortController(); setLoading(true); setError(""); setNeedsRefresh(false);
    Promise.all([api<{items: CompanyPartner[]}>(scope(`/data/business-partners/${encodeURIComponent(businessPartnerId)}/companies`), "GET", undefined, {signal: controller.signal}), api<{items: CompanyOption[]}>(scope("/business-partner-companies/options"), "GET", undefined, {signal: controller.signal})])
      .then(([relations, companies]) => {if (alive) {setItems(relations.items); setOptions(companies.items);}})
      .catch(e => {if (alive) {setItems([]); setOptions([]); setNeedsRefresh(true); setError(onError(e));}}).finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [businessPartnerId, readable, session, scope, onError, revision]);
  if (!businessPartnerId || !readable) return null;
  // Le opzioni sono autorevoli per la precisa azienda, non l'unione dei permessi di sessione.
  const authority = (companyId: string, action: string) => options.some(company => company.id === companyId && company.permissions.includes(action));
  const creatable = options.filter(company => company.is_enabled && company.permissions.includes("create") && !items.some(row => row.company_id === company.id));
  const disabled = loading || busy || needsRefresh;
  const managed = items.find(row => row.company_id === managedCompany);
  const refresh = () => {if (!locked.current) {setOperation(null); setAssociation(null); setRevision(v => v + 1);}};
  const requestOperation = (row: CompanyPartner, role?: PartnerRoleCode) => {
    if (disabled || locked.current || !authority(row.company_id, "update")) return;
    const current = role ? row.roles.find(entry => entry.role_code === role)?.status : row.status;
    setError(""); setOperation({companyId: row.company_id, role, status: current === "ACTIVE" ? "BLOCKED" : "ACTIVE", version: row.version});
  };
  async function commit(event: {preventDefault: () => void; stopPropagation?: () => void}, mode: "associate" | "operation") {
    event.preventDefault(); event.stopPropagation?.();
    if (disabled || locked.current) return;
    if (mode === "associate" && (!association || !creatable.some(company => company.id === association.companyId))) return;
    if (mode === "operation" && (!operation || !authority(operation.companyId, "update"))) return;
    locked.current = true; setBusy(true); setError("");
    let accepted = false;
    try {
      const pending = operation;
      const companyId = mode === "associate" ? association!.companyId : pending!.companyId;
      const base = `/companies/${encodeURIComponent(companyId)}/business-partners`;
      const saved = await api<CompanyPartner>(scope(mode === "associate" ? base : `${base}/${encodeURIComponent(businessPartnerId)}${pending!.role ? `/roles/${pending!.role}` : ""}`), mode === "associate" ? "POST" : pending!.role ? "PUT" : "PATCH", mode === "associate" ? {businessPartnerId, roles: association!.roles} : {status: pending!.status, expectedVersion: pending!.version});
      accepted = true;
      if (!mounted.current) return;
      setItems(current => [...current.filter(row => row.company_id !== companyId), saved]);
      setAssociation(null); setOperation(null);
      // Una verifica fallita non deve consentire di ripetere un comando già committato.
      const current = await api<{items: CompanyPartner[]}>(scope(`/data/business-partners/${encodeURIComponent(businessPartnerId)}/companies`));
      if (mounted.current) setItems(current.items);
    } catch (e) {
      if (mounted.current) {setError(onError(e)); if (accepted || e instanceof ApiError && (e.code === "stale_version" || e.code === "company_partner_exists" || e.status === 0)) setNeedsRefresh(true);}
    } finally {locked.current = false; if (mounted.current) setBusy(false);}
  }
  const errorNotice = error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null;
  function statusButton(row: CompanyPartner, role?: PartnerRoleCode) {
    const current = role ? row.roles.find(entry => entry.role_code === role) : row;
    const label = `${t(!current ? "assign" : current.status === "ACTIVE" ? "block" : "activate")} ${role ? t(role) : t("relationshipStatus")} — ${row.company_name}`;
    const Icon = current?.status === "ACTIVE" ? Ban : Check;
    return <Button type="button" size="icon" variant="ghost" className="size-8 shrink-0" disabled={disabled} title={label} aria-label={label} data-action={role ? `${current ? "toggle" : "assign"}-${role}` : "toggle-relation"} data-company-action={role ? `${current ? "role" : "assign"}-${row.company_id}-${role}` : `relationship-${row.company_id}`} onClick={() => requestOperation(row, role)}><Icon size={16} aria-hidden /></Button>;
  }
  return <Card data-bp-companies data-bp-company-relations className="gap-3 p-4 sm:p-6" aria-busy={loading || busy}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{t("title")}</h3><div className="flex gap-2"><Button type="button" variant="ghost" size="icon" data-action="refresh-company-relations" aria-label={a("refresh")} disabled={loading || busy} onClick={refresh}><RefreshCw size={16} /></Button>{creatable.length > 0 && <Button type="button" variant="outline" size="sm" data-action="associate-company" disabled={disabled} onClick={() => {if (!disabled && !locked.current) {setError(""); setAssociation({companyId: "", roles: []});}}}><Plus size={16} />{t("add")}</Button>}</div></div>
    {errorNotice}
    <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>{t("company")}</TableHead><TableHead>{t("relationshipStatus")}</TableHead><TableHead>{t("assignedRoles")}</TableHead><TableHead>{t("usableRoles")}</TableHead><TableHead className={companyPartnerActionsClass}>{a("actions")}</TableHead></TableRow></TableHeader><TableBody>
      {!items.length && <TableRow><TableCell colSpan={5}>{a(loading ? "loading" : "empty")}</TableCell></TableRow>}
      {items.map(row => <TableRow key={row.id} data-company-id={row.company_id}><TableCell className="min-w-40 whitespace-normal">{row.company_name}</TableCell><TableCell><Badge variant="secondary">{t(row.status)}</Badge></TableCell><TableCell className="whitespace-normal">{row.roles.map(role => `${t(role.role_code)} · ${t(role.status)}`).join(", ") || "—"}</TableCell><TableCell>{row.usable_roles.map(role => t(role)).join(", ") || "—"}</TableCell><TableCell className={companyPartnerActionsClass}>{authority(row.company_id, "update") && <div className="flex justify-end gap-1">{statusButton(row)}<Button type="button" size="icon" variant="ghost" className="size-8 shrink-0" data-action={`manage-company-${row.company_id}`} disabled={disabled} aria-label={`${t("edit")} — ${row.company_name}`} title={t("edit")} onClick={() => {if (!disabled) {setError(""); setManagedCompany(row.company_id);}}}><Pencil size={16} aria-hidden /></Button></div>}</TableCell></TableRow>)}
    </TableBody></Table></div>
    {association && <Dialog open onOpenChange={open => {if (!open && !locked.current) setAssociation(null);}}><DialogContent data-bp-company-editor="associate" aria-describedby={undefined}><DialogHeader><DialogTitle>{t("add")}</DialogTitle></DialogHeader><form data-company-association-form className="space-y-4" onSubmit={event => commit(event, "associate")}>
      {errorNotice}<div className="space-y-2"><Label htmlFor="bp-company-id">{t("company")}</Label><Select value={association.companyId} disabled={disabled} onValueChange={value => {if (!disabled && creatable.some(company => company.id === value)) setAssociation(current => current ? {...current, companyId: value} : current);}}><SelectTrigger id="bp-company-id" className="w-full"><SelectValue placeholder={t("company")} /></SelectTrigger><SelectContent>{creatable.map(company => <SelectItem key={company.id} value={company.id}>{company.name}{company.code ? ` · ${company.code}` : ""}</SelectItem>)}</SelectContent></Select></div>
      <fieldset className="space-y-3"><legend className="mb-2 font-medium">{t("assignedRoles")}</legend>{roleCodes.map(role => <Label key={role} className="flex items-center gap-2"><Checkbox id={`bp-company-${role}`} checked={association.roles.includes(role)} disabled={disabled} onCheckedChange={checked => {if (!disabled) setAssociation(current => current ? {...current, roles: checked === true ? [...new Set([...current.roles, role])] : current.roles.filter(value => value !== role)} : current);}} />{t(role)}</Label>)}</fieldset>
      <DialogFooter><Button type="button" variant="outline" data-action="cancel-company-association" disabled={busy} onClick={() => {if (!locked.current) setAssociation(null);}}>{a("cancel")}</Button><Button type="submit" data-action="confirm-company-association" disabled={disabled || !creatable.some(company => company.id === association.companyId)}>{t("confirm")}</Button></DialogFooter>
    </form></DialogContent></Dialog>}
    {managed && authority(managed.company_id, "update") && <Dialog open onOpenChange={open => {if (!open && !locked.current) setManagedCompany(null);}}><DialogContent data-bp-company-editor="manage" aria-describedby={undefined}><DialogHeader><DialogTitle>{managed.company_name}</DialogTitle></DialogHeader>{errorNotice}<div className="flex items-center justify-between"><span>{t("relationshipStatus")} · {t(managed.status)}</span>{statusButton(managed)}</div><div className="space-y-3">{roleCodes.map(role => {const assigned = managed.roles.find(entry => entry.role_code === role); return <div key={role} data-company-id={managed.company_id} className="flex items-center justify-between gap-3"><Label className="flex items-center gap-2"><Checkbox id={`bp-existing-${managed.company_id}-${role}`} checked={Boolean(assigned)} disabled={Boolean(assigned) || disabled} onCheckedChange={checked => {if (checked === true && !assigned) requestOperation(managed, role);}} />{t(role)}{assigned && <Badge variant="secondary">{t(assigned.status)}</Badge>}</Label>{statusButton(managed, role)}</div>;})}</div><DialogFooter><Button type="button" variant="outline" disabled={busy} data-action="close-company-management" onClick={() => {if (!locked.current) setManagedCompany(null);}}>{a("close")}</Button></DialogFooter></DialogContent></Dialog>}
    {operation && <AlertDialog open onOpenChange={open => {if (!open && !locked.current) setOperation(null);}}><AlertDialogContent data-bp-company-confirmation><AlertDialogHeader><AlertDialogTitle>{t("confirmChange")}</AlertDialogTitle><AlertDialogDescription>{options.find(company => company.id === operation.companyId)?.name} — {operation.role ? t(operation.role) : t("relationshipStatus")} — {t(operation.status)}. {t("confirmChangeDescription")}</AlertDialogDescription></AlertDialogHeader>{errorNotice}<AlertDialogFooter><AlertDialogCancel type="button" disabled={busy} data-action="cancel-company-operation" onClick={() => {if (!locked.current) setOperation(null);}}>{a("cancel")}</AlertDialogCancel><AlertDialogAction type="button" disabled={disabled} data-action="confirm-company-operation" onClick={event => commit(event, "operation")}>{t("confirm")}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>}
  </Card>;
}
