"use client";
import {useCallback, useEffect, useMemo, useRef, useState, type ReactNode} from "react";
import {useLocale, useTranslations} from "next-intl";
import {Plus, RefreshCw, Pencil, Eye, Trash2} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Checkbox} from "@/components/ui/checkbox";
import {Textarea} from "@/components/ui/textarea";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {Card} from "@/components/ui/card";
import {Badge} from "@/components/ui/badge";
import {Table, TableHeader, TableBody, TableRow, TableHead, TableCell} from "@/components/ui/table";
import {Alert, AlertDescription} from "@/components/ui/alert";
import {api, ApiError} from "@/lib/api";
import type {PartnerNumbering} from "@/components/business-partner-numbering";
import {can, countryLabel, type Row, type Session} from "@/lib/model";
import {countryCodes} from "@/lib/country-codes";
import {AddressAutocomplete, addressSelection, type AddressField, type AddressSuggestion} from "@/components/address-autocomplete";
import {Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter} from "@/components/ui/dialog";
import {AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction} from "@/components/ui/alert-dialog";
import {SiteCountrySelect} from "@/components/site-country-select";
import {BusinessPartnerCompanies, companyPartnerReadable} from "@/components/business-partner-companies";
import {CompanyBusinessPartners} from "@/components/company-business-partners";

type Props = {session: Session; scope: (path: string) => string; onError: (error: unknown) => string; heading?: ReactNode; tenantId?: string | null};
function storageKey(session: Session, tenantId?: string | null) {
  const tenant = session.isSuperAdmin ? tenantId : session.tenantId;
  return session.id && tenant ? `bp-refresh:v1:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}` : null;
}
function readState(key: string | null): any {
  try {return key ? JSON.parse(sessionStorage.getItem(key) || "null") : null;} catch {return null;}
}
function writeState(key: string | null, value: unknown) {
  try {if (!key) return false; sessionStorage.setItem(key, JSON.stringify(value)); return true;} catch {return false;}
}
/** Call on an explicit workspace reset, with the same tenantId passed to the workspace. */
export function resetBusinessPartnerRecovery(session: Session, tenantId?: string | null) {
  try {
    const key = storageKey(session, tenantId), stored = readState(key);
    if (!key) return;
    if (stored?.draft?.id === null && (stored.draft.createUncertain || stored.draft.verificationId)) {
      writeState(key, {editor: {id: null}, draft: stored.draft});
    } else sessionStorage.removeItem(key);
  } catch { /* Storage can be unavailable. */ }
}
export function clearBusinessPartnerRecoveries(session: Session) {
  try {
    const prefix = `bp-refresh:v1:${encodeURIComponent(session.id)}:`;
    for (let index = sessionStorage.length - 1; index >= 0; index--) {
      const key = sessionStorage.key(index);
      if (!key?.startsWith(prefix)) continue;
      const stored = readState(key), pending = stored?.draft;
      if (pending?.id === null && (pending.createUncertain || pending.verificationId)) {
        const marker = typeof pending.verificationId === "string" && pending.verificationId ? {id: null, verificationId: pending.verificationId} : {id: null, createUncertain: true};
        writeState(key, {editor: {id: null}, draft: marker});
      } else sessionStorage.removeItem(key);
    }
  } catch { /* Storage can be unavailable. */ }
}
type Result = {items: Row[]; total: number; page: number; pageSize: number};
export function BusinessPartnerWorkspace({session, scope, onError, heading, tenantId}: Props) {
  const t = useTranslations("businessPartners"), a = useTranslations("app");
  const readable = can(session, "business-partners", "read");
  const [result, setResult] = useState<Result>({items: [], total: 0, page: 1, pageSize: 25});
  const [search, setSearch] = useState(""), [query, setQuery] = useState(""), [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [editor, setEditor] = useState<{id: string | null} | null>(null);
  const [saved, setSaved] = useState(false);
  const key = storageKey(session, tenantId);
  const [restoredKey, setRestoredKey] = useState<string | null | undefined>(undefined);
  const [companyView, setCompanyView] = useState(false);
  const activeCompanyView = companyView && companyPartnerReadable(session);
  useEffect(() => {
    const stored = readState(key);
    setSearch(typeof stored?.search === "string" ? stored.search : "");
    setQuery(typeof stored?.search === "string" ? stored.search : "");
    setPage(Number.isSafeInteger(stored?.page) && stored.page > 0 ? stored.page : 1);
    setCompanyView(stored?.companyView === true && companyPartnerReadable(session));
    const id = stored?.editor?.id;
    setEditor(stored?.editor && (id === null ? can(session, "business-partners", "create") : typeof id === "string" && can(session, "business-partners", "read")) ? {id} : null);
    setRestoredKey(key);
  }, [key]);
  useEffect(() => {if (restoredKey === key) writeState(key, {...readState(key), search, page, editor, companyView});}, [key, restoredKey, search, page, editor, companyView]);
  useEffect(() => {if (restoredKey !== key || search === query) return; const timer = setTimeout(() => {setQuery(search); setPage(1);}, 300); return () => clearTimeout(timer);}, [search, query, key, restoredKey]);
  useEffect(() => {
    let alive = true; const controller = new AbortController();
    if (!readable || activeCompanyView) {setLoading(false); return;}
    setLoading(true); setError("");
    api<Result>(scope(`/data/business-partners?page=${page}&pageSize=25&search=${encodeURIComponent(query)}`), "GET", undefined, {signal: controller.signal})
      .then(data => {if (alive) {setResult(data); if (!data.items.length && page > 1) setPage(page - 1);}})
      .catch(e => {if (alive) {setResult({items: [], total: 0, page, pageSize: 25}); setError(onError(e));}})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [session, scope, page, query, revision, onError, readable, activeCompanyView]);
  if (editor) {
    const content = <BusinessPartnerEditor {...{session, scope, onError, tenantId}} id={editor.id} onClose={() => setEditor(null)} onSaved={() => {setEditor(null); setSaved(true); setRevision(v => v + 1);}} />;
    return heading ? <div className="space-y-4"><div className="page-heading">{heading}</div>{content}</div> : content;
  }
  return <div className="space-y-4">
    <div className="page-heading flex-wrap">{heading}{can(session, "business-partners", "create") && <Button className="ml-auto" onClick={() => {setSaved(false); setEditor({id: null});}}><Plus size={16} />{t("new")}</Button>}</div>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {saved && <p role="status" className="success">{a("saved")}</p>}
    {companyPartnerReadable(session) && <div className="flex flex-wrap gap-2"><Button type="button" variant={!companyView ? "default" : "outline"} data-action="partner-identity-view" aria-pressed={!companyView} onClick={() => setCompanyView(false)}>{t("identity")}</Button><Button type="button" variant={companyView ? "default" : "outline"} data-action="partner-company-view" aria-pressed={companyView} onClick={() => setCompanyView(true)}>{t("byCompany")}</Button></div>}
    {companyView && companyPartnerReadable(session) && <CompanyBusinessPartners {...{session, scope, onError}} recoveryKey={key} onOpenPartner={id => {setSaved(false); setEditor({id});}} />}
    {readable && !activeCompanyView && <Card className="gap-0 overflow-hidden py-0">
      <div className="table-toolbar"><Input aria-label={t("search")} placeholder={t("search")} value={search} onChange={e => setSearch(e.target.value)} /><span className="shrink-0 text-sm">{result.total} {a("records", {count: result.total})}</span><Button variant="ghost" size="icon" aria-label={a("refresh")} disabled={loading} onClick={() => setRevision(v => v + 1)}><RefreshCw size={16} /></Button></div>
      <div className="table-scroll" aria-busy={loading}><Table><TableHeader><TableRow>{["code", "displayName", "kind", "status"].map(key => <TableHead key={key} kind={key === "status" ? "status" : "text"}>{t(key)}</TableHead>)}<TableHead kind="actions" className={actionColumnClassName}>{a("actions")}</TableHead></TableRow></TableHeader>
        <TableBody>{!result.items.length ? <TableRow><TableCell colSpan={5}><p className="table-empty" role="status">{loading ? a("loading") : a("empty")}</p></TableCell></TableRow> : result.items.map(row => {
          const name = String(row.legal_name || [row.first_name, row.last_name].filter(Boolean).join(" ") || row.code);
          return <TableRow key={row.id}><TableCell kind="text">{String(row.code ?? "—")}</TableCell><TableCell kind="text" className="min-w-48 whitespace-normal font-medium">{name}</TableCell><TableCell kind="text">{t(String(row.kind))}</TableCell><TableCell kind="status"><Badge variant="secondary">{t(String(row.status))}</Badge></TableCell><TableCell kind="actions" className={actionColumnClassName}><Button variant="ghost" size="icon" aria-label={`${can(session, "business-partners", "update") ? a("edit") : a("details")} ${name}`} onClick={() => {setSaved(false); setEditor({id: row.id});}}><Pencil size={16} /></Button></TableCell></TableRow>;
        })}</TableBody></Table></div>
      <div className="pagination"><span>{a("page")} {page} {a("of")} {Math.max(1, Math.ceil(result.total / 25))}</span><div><Button variant="outline" disabled={loading || page <= 1} onClick={() => setPage(v => v - 1)}>{a("previous")}</Button><Button variant="outline" disabled={loading || page * 25 >= result.total} onClick={() => setPage(v => v + 1)}>{a("next")}</Button></div></div>
    </Card>}
  </div>;
}
type TaxIdentifier = {country_code: string; identifier_type: string; value: string};
type AddressUsage = {usage: string; is_default: boolean};
type PartnerAddress = {label: string; street: string; street_number: string; postal_code: string; city: string; province: string; country_code: string; additional_info: string; usages: AddressUsage[]};
type ContactChannel = {channel_type: string; value: string; purpose: string; is_primary: boolean};
type PartnerDraft = {kind: string; legal_name: string; first_name: string; last_name: string; status: string; code: string; tax_identifiers: TaxIdentifier[]; addresses: PartnerAddress[]; contact_channels: ContactChannel[]};
type PartnerRecord = PartnerDraft & {id: string; version: number};
type RelatedKind = "tax" | "address" | "contact";
const actionColumnClassName = "w-[120px] min-w-[120px] max-w-[120px]";
const actionIcons = {details: Eye, edit: Pencil, remove: Trash2};
type RelatedEditor = {kind: "tax"; row: TaxIdentifier; index: number; mode: "add" | "edit" | "details"} | {kind: "address"; row: PartnerAddress; index: number; mode: "add" | "edit" | "details"} | {kind: "contact"; row: ContactChannel; index: number; mode: "add" | "edit" | "details"};
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
function contactError(contact: ContactChannel) {
  const value = contact.value.trim();
  if (["EMAIL", "PEC"].includes(contact.channel_type)) return value.length > 254 || !/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(value) ? "invalid_contact_email" : null;
  if (["PHONE", "MOBILE"].includes(contact.channel_type)) return value.length > 50 || !/[0-9]/.test(value) || !/^[+0-9() .\-/#xXeEtT]+$/.test(value) ? "invalid_contact_phone" : null;
  try {const url = new URL(value); return !["http:", "https:"].includes(url.protocol) || !url.hostname || Boolean(url.username || url.password) ? "invalid_contact_website" : null;} catch {return "invalid_contact_website";}
}
const emptyDraft = (): PartnerDraft => ({kind: "ORGANIZATION", legal_name: "", first_name: "", last_name: "", status: "ACTIVE", code: "", tax_identifiers: [], addresses: [], contact_channels: []});
const relatedKeys = {tax: "taxIdentifiers", address: "addresses", contact: "contactChannels"} as const;
function serializeCollections(draft: PartnerDraft) {
  return {
    taxIdentifiers: draft.tax_identifiers.map(({country_code, identifier_type, value}) => ({country_code, identifier_type, value})),
    addresses: draft.addresses.map(({label, street, street_number, postal_code, city, province, country_code, additional_info, usages}) => ({label, street, street_number, postal_code, city, province, country_code, additional_info, usages: usages.map(({usage, is_default}) => ({usage, is_default}))})),
    contactChannels: draft.contact_channels.map(({channel_type, value, purpose, is_primary}) => ({channel_type, value, purpose, is_primary})),
  };
}
export function BusinessPartnerEditor({session, scope, onError, id, onClose, onSaved, tenantId}: Props & {id: string | null; onClose: () => void; onSaved: () => void}) {
  const locale = useLocale();
  const countryOptions = useMemo(() => countryCodes.map(value => ({value, label: countryLabel(value, locale)}))
    .sort((a, b) => a.label.localeCompare(b.label, locale)), [locale]);
  const countryLabels = new Map(countryOptions.map(option => [option.value, option.label]));
  const a = useTranslations("app"), t = useTranslations("businessPartners");
  const [draft, setDraft] = useState<PartnerDraft>(emptyDraft), [expectedVersion, setExpectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(Boolean(id)), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [fieldError, setFieldError] = useState<{id: string; message: string} | null>(null);
  const locked = useRef(false);
  const [related, setRelated] = useState<RelatedEditor | null>(null);
  const [removal, setRemoval] = useState<{kind: RelatedKind; index: number} | null>(null);
  const [numberingMode, setNumberingMode] = useState<"AUTO" | "MANUAL" | null>(null);
  const [verificationId, setVerificationId] = useState<string | null>(null);
  const [createUncertain, setCreateUncertain] = useState(false);
  const numberingReadable = can(session, "business-partner-numbering", "read");
  const editable = can(session, "business-partners", id ? "update" : "create"), baseDisabled = !editable || loading || busy || Boolean(verificationId || createUncertain), disabled = baseDisabled || related?.mode === "details";
  const key = storageKey(session, tenantId);
  const [recoveryReady, setRecoveryReady] = useState(false);
  const recovery = useRef<any>(null);
  function clearRecovery() {const stored = readState(key); if (stored) writeState(key, {...stored, editor: null, draft: null});}
  useEffect(() => {
    const saved = readState(key)?.draft;
    if (editable && !id && saved?.id === null) {
      setVerificationId(typeof saved.verificationId === "string" ? saved.verificationId : null);
      setCreateUncertain(Boolean(saved.createUncertain));
    }
    if (editable && saved?.id === id && saved?.draft && Array.isArray(saved.draft.tax_identifiers) && Array.isArray(saved.draft.addresses) && Array.isArray(saved.draft.contact_channels) && (!id || Number.isSafeInteger(saved.expectedVersion))) {
      recovery.current = saved;
      if (!id) {setDraft(saved.draft); setExpectedVersion(saved.expectedVersion); setRelated(saved.related ?? null); setVerificationId(saved.verificationId ?? null); setCreateUncertain(Boolean(saved.createUncertain));}
    }
    setRecoveryReady(true);
  }, [key, id]);
  useEffect(() => {
    if (recoveryReady && editable && (!id || !loading) && (!id || expectedVersion !== null)) writeState(key, {...readState(key), draft: {id, draft, expectedVersion, related, verificationId, createUncertain}});
  }, [key, id, recoveryReady, editable, loading, draft, expectedVersion, related, verificationId, createUncertain]);
  const geographyScope = useCallback((path: string) => scope(`${path}${path.includes("?") ? "&" : "?"}resource=business-partners`), [scope]);
  useEffect(() => {
    if (id || !numberingReadable) return;
    let alive = true; const controller = new AbortController();
    api<PartnerNumbering>(scope("/business-partner-numbering"), "GET", undefined, {signal: controller.signal})
      .then(config => {if (alive) setNumberingMode(config.mode);})
      .catch(() => {}); // La lettura della configurazione non è un prerequisito della creazione.
    return () => {alive = false; controller.abort();};
  }, [id, numberingReadable, scope]);
  useEffect(() => {
    if (!id) return;
    let alive = true; const controller = new AbortController();
    setLoading(true); setError("");
    api<PartnerRecord>(scope(`/data/business-partners/${encodeURIComponent(id)}`), "GET", undefined, {signal: controller.signal})
      .then(record => {if (alive) {const saved = recovery.current; if (saved && saved.id === id) {setDraft(saved.draft); setExpectedVersion(saved.expectedVersion); setRelated(saved.related ?? null); setVerificationId(saved.verificationId ?? null); setCreateUncertain(Boolean(saved.createUncertain));} else {setDraft({...emptyDraft(), ...record, legal_name: record.legal_name ?? "", first_name: record.first_name ?? "", last_name: record.last_name ?? ""}); setExpectedVersion(record.version);}}})
      .catch(e => {if (alive) setError(onError(e));})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [id, scope, onError]);
  const set = (key: keyof PartnerDraft, value: unknown) => {if (!disabled) {setDraft(current => ({...current, [key]: value})); setError(""); setFieldError(null);}};
  function showError(error: unknown, source = draft, preserveRelated = false) {
    const message = onError(error), field = error instanceof ApiError ? error.field : undefined;
    let target: {id: string; label: string} | undefined;
    const identity = /^values\.(legal_name|first_name|last_name|kind|status|code)$/.exec(field ?? "");
    if (identity) target = {id: `bp-${identity[1]}`, label: t(identity[1])};
    const tax = /^taxIdentifiers\[(\d+)\]\.(country_code|identifier_type|value|normalized_value)$/.exec(field ?? "");
    if (tax && source.tax_identifiers[Number(tax[1])]) {
      const row = source.tax_identifiers[Number(tax[1])];
      const key = tax[2] === "country_code" ? "country" : tax[2] === "identifier_type" ? "type" : "value";
      const label = key === "country" ? "country" : key === "type" ? "identifierType" : ["VAT", "FISCAL_CODE", "FOREIGN_TAX_ID"].includes(row.identifier_type) ? row.identifier_type : "identifierValue";
      target = {id: `bp-tax-${tax[1]}-${key}`, label: `${t("taxIdentifier")} ${Number(tax[1]) + 1} — ${t(label)}`};
    }
    const address = /^addresses\[(\d+)\]\.(label|street|street_number|postal_code|city|province|country_code|additional_info)$/.exec(field ?? "");
    if (address && source.addresses[Number(address[1])]) {
      const key = address[2] === "country_code" ? "country" : address[2];
      target = {id: `bp-address-${address[1]}-${key}`, label: `${t("address")} ${Number(address[1]) + 1} — ${t(key)}`};
    }
    const usage = /^addresses\[(\d+)\]\.usages\[(\d+)\]\.(usage|is_default)$/.exec(field ?? "");
    if (usage) {
      const row = source.addresses[Number(usage[1])]?.usages[Number(usage[2])];
      if (row && ["REGISTERED", "BILLING", "SHIPPING", "CORRESPONDENCE"].includes(row.usage)) target = {id: `bp-address-${usage[1]}-${row.usage}${usage[3] === "is_default" ? "-default" : ""}`, label: `${t("address")} ${Number(usage[1]) + 1} — ${t(row.usage)}${usage[3] === "is_default" ? ` — ${t("default")}` : ""}`};
    }
    const contact = /^contactChannels\[(\d+)\]\.(channel_type|value|purpose|is_primary)$/.exec(field ?? "");
    if (contact && source.contact_channels[Number(contact[1])]) {
      const row = source.contact_channels[Number(contact[1])];
      const key = contact[2] === "channel_type" ? "type" : contact[2] === "is_primary" ? "primary" : contact[2];
      const label = key === "type" ? "channelType" : key === "value" && ["EMAIL", "PHONE", "MOBILE", "PEC", "WEBSITE"].includes(row.channel_type) ? row.channel_type : key === "value" ? "contactValue" : key;
      target = {id: `bp-contact-${contact[1]}-${key}`, label: `${t("contact")} ${Number(contact[1]) + 1} — ${t(label)}`};
    }
    const rowTarget = /^bp-(tax|address|contact)-(\d+)-/.exec(target?.id ?? "");
    if (rowTarget && !preserveRelated) openRelated(rowTarget[1] as RelatedKind, Number(rowTarget[2]), "edit", true);
    setError(target ? `${target.label}: ${message}` : message);
    setFieldError(target ? {id: target.id, message} : null);
  }
  const invalid = (fieldId: string) => ({"aria-invalid": fieldError?.id === fieldId || undefined, "aria-describedby": fieldError?.id === fieldId ? `${fieldId}-error` : undefined});
  const feedback = (fieldId: string) => fieldError?.id === fieldId ? <p id={`${fieldId}-error`} className="text-sm text-destructive">{fieldError.message}</p> : null;
  function text(key: "legal_name" | "first_name" | "last_name" | "code", required = false) {
    return <div className="space-y-2"><Label htmlFor={`bp-${key}`} required={required}>{t(key)}</Label><Input id={`bp-${key}`} {...invalid(`bp-${key}`)} value={draft[key]} required={required} disabled={disabled} onChange={e => set(key, e.target.value)} />{feedback(`bp-${key}`)}</div>;
  }
  function choice(key: "kind" | "status", options: string[]) {
    return <div className="space-y-2"><Label htmlFor={`bp-${key}`} required>{t(key)}</Label><Select value={draft[key]} disabled={disabled} onValueChange={value => set(key, value)}><SelectTrigger id={`bp-${key}`} {...invalid(`bp-${key}`)} className="w-full"><SelectValue /></SelectTrigger><SelectContent>{options.map(option => <SelectItem key={option} value={option}>{t(option)}</SelectItem>)}</SelectContent></Select>{feedback(`bp-${key}`)}</div>;
  }
  function input(fieldId: string, label: string, value: string, onChange: (value: string) => void, type = "text", required = false) {
    return <div className="space-y-2"><Label htmlFor={fieldId} required={required}>{t(label)}</Label><Input id={fieldId} {...invalid(fieldId)} type={type} value={value ?? ""} disabled={disabled} required={required} onChange={e => {if (!disabled) onChange(e.target.value);}} />{feedback(fieldId)}</div>;
  }
  function select(fieldId: string, label: string, value: string, options: string[], onChange: (value: string) => void, country = false) {
    const entries = country ? [...countryOptions.map(option => option.value), ...(value && !countryLabels.has(value) ? [value] : [])] : options;
    return <div className="space-y-2"><Label htmlFor={fieldId} required>{t(label)}</Label><Select value={value} disabled={disabled} required onValueChange={next => {if (!disabled) onChange(next);}}><SelectTrigger id={fieldId} {...invalid(fieldId)} className="w-full"><SelectValue /></SelectTrigger><SelectContent>{entries.map(option => <SelectItem key={option} value={option}>{country ? countryLabels.get(option) ?? countryLabel(option, locale) : t(option)}</SelectItem>)}</SelectContent></Select>{feedback(fieldId)}</div>;
  }
  const updateTax = (_index: number, changes: Partial<TaxIdentifier>) => {if (!disabled) {setError(""); setFieldError(null);} if (!disabled) setRelated(current => current?.kind === "tax" ? {...current, row: {...current.row, ...changes}} : current);};
  const updateAddress = (_index: number, changes: Partial<PartnerAddress>) => {if (!disabled) {setError(""); setFieldError(null);} if (!disabled) setRelated(current => current?.kind === "address" ? {...current, row: {...current.row, ...changes}} : current);};
  const updateContact = (_index: number, changes: Partial<ContactChannel>) => {if (!disabled) {setError(""); setFieldError(null);} if (!disabled) setRelated(current => current?.kind === "contact" ? {...current, row: {...current.row, ...changes}} : current);};
  function selectAddress(index: number, field: AddressField, item: AddressSuggestion) {
    if (disabled || related?.kind !== "address") return;
    const old = related.row;
    const selected = addressSelection({...old, address: old.street}, field, item);
    updateAddress(index, {street: String(selected.address ?? ""), city: String(selected.city ?? ""), province: String(selected.province ?? ""), postal_code: String(selected.postal_code ?? ""), country_code: String(selected.country_code ?? "")});
  }
  function openRelated(kind: RelatedKind, index: number, mode: RelatedEditor["mode"], validation = false) {
    if (loading || (!validation && (busy || locked.current)) || verificationId || (mode !== "details" && !editable)) return;
    setFieldError(null);
    if (kind === "tax") setRelated({kind, index, mode, row: clone(draft.tax_identifiers[index] ?? {country_code: "IT", identifier_type: "VAT", value: ""})});
    if (kind === "address") setRelated({kind, index, mode, row: clone(draft.addresses[index] ?? {label: "", street: "", street_number: "", postal_code: "", city: "", province: "", country_code: "IT", additional_info: "", usages: []})});
    if (kind === "contact") setRelated({kind, index, mode, row: clone(draft.contact_channels[index] ?? {channel_type: "EMAIL", value: "", purpose: "", is_primary: false})});
  }
  async function commitRelated(next: PartnerDraft, kind: RelatedKind) {
    if (!id) return false;
    if (locked.current || baseDisabled || expectedVersion === null) return false;
    locked.current = true; setBusy(true); setError(""); setFieldError(null);
    try {
      const key = relatedKeys[kind];
      const record = await api<PartnerRecord>(scope(`/data/business-partners/${encodeURIComponent(id)}/save`), "PUT", {
        values: {}, [key]: serializeCollections(next)[key], expectedVersion,
      });
      // La risposta aggiorna figli e revisione, non l'identità ancora in bozza.
      setDraft(current => ({...current, tax_identifiers: record.tax_identifiers, addresses: record.addresses, contact_channels: record.contact_channels}));
      setExpectedVersion(record.version);
      return true;
    } catch (e) {showError(e, next, true); return false;}
    finally {locked.current = false; setBusy(false);}
  }
  async function applyRelated(event: React.FormEvent) {
    event.preventDefault(); event.stopPropagation();
    if (!related || disabled || locked.current) return;
    if (related.kind === "contact") {
      const code = contactError(related.row);
      if (code) {const message = onError(new ApiError(code, 400)); setFieldError({id: `bp-contact-${related.index}-value`, message}); return;}
    }
    const child = related;
    const next = ((current: PartnerDraft) => {
      if (child.kind === "tax") {const rows = [...current.tax_identifiers]; rows[child.index] = clone(child.row); return {...current, tax_identifiers: rows};}
      if (child.kind === "address") {
        const defaults = new Set(child.row.usages.filter(entry => entry.is_default).map(entry => entry.usage));
        const rows = current.addresses.map(row => ({...row, usages: row.usages.map(entry => defaults.has(entry.usage) ? {...entry, is_default: false} : entry)}));
        rows[child.index] = clone(child.row); return {...current, addresses: rows};
      }
      const rows = current.contact_channels.map(row => child.row.is_primary && row.channel_type === child.row.channel_type ? {...row, is_primary: false} : row);
      rows[child.index] = clone(child.row); return {...current, contact_channels: rows};
    })(draft);
    if (id) {if (!await commitRelated(next, child.kind)) return;}
    else setDraft(next);
    setRelated(null); setFieldError(null); setError("");
  }
  async function removeRelated(event: React.MouseEvent) {
    event.preventDefault(); // La conferma resta aperta fino al commit riuscito.
    if (!removal || baseDisabled || locked.current) return;
    const key = removal.kind === "tax" ? "tax_identifiers" : removal.kind === "address" ? "addresses" : "contact_channels";
    const next = {...draft, [key]: draft[key].filter((_, index) => index !== removal.index)};
    if (id) {if (!await commitRelated(next, removal.kind)) return;}
    else setDraft(next);
    setRemoval(null); setFieldError(null); setError("");
  }
  function checkbox(fieldId: string, label: string, checked: boolean, onChange: (checked: boolean) => void, extraDisabled = false) {
    return <div className="space-y-2"><div className="flex items-center gap-2"><Checkbox id={fieldId} {...invalid(fieldId)} checked={checked} disabled={disabled || extraDisabled} onCheckedChange={value => {if (!disabled && !extraDisabled) onChange(value === true);}} /><Label htmlFor={fieldId}>{t(label)}</Label></div>{feedback(fieldId)}</div>;
  }
  function rowFields() {
    if (!related) return null;
    const index = related.index;
    if (related.kind === "tax") {const tax = related.row; return (<fieldset key={index} className="space-y-4 rounded-lg border p-4" disabled={disabled}><legend className="px-1 text-sm font-medium">{t("taxIdentifier")} {index + 1}</legend><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {select(`bp-tax-${index}-country`, "country", tax.country_code, countryCodes, value => updateTax(index, {country_code: value}), true)}
          {select(`bp-tax-${index}-type`, "identifierType", tax.identifier_type, ["VAT", "FISCAL_CODE", "FOREIGN_TAX_ID"], value => updateTax(index, {identifier_type: value}))}
          {input(`bp-tax-${index}-value`, "identifierValue", tax.value, value => updateTax(index, {value}), "text", true)}
        </div></fieldset>);}
    if (related.kind === "address") {const address = related.row; return (<fieldset key={index} className="space-y-4 rounded-lg border p-4" disabled={disabled}><legend className="px-1 text-sm font-medium">{t("address")} {index + 1}</legend>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{(["label", "street", "street_number", "postal_code", "city", "province"] as const).map(key => {
            const fieldId = `bp-address-${index}-${key}`;
            return <div key={key}>{["street", "postal_code", "city", "province"].includes(key) ? <div className="space-y-2"><Label htmlFor={fieldId} required={["street", "postal_code", "city"].includes(key)}>{t(key)}</Label>
              <AddressAutocomplete id={fieldId} {...invalid(fieldId)} field={key === "street" ? "address" : key as AddressField} value={address[key] ?? ""} context={{...address, address: address.street}} scope={geographyScope}
                disabled={disabled} required={["street", "postal_code", "city"].includes(key)} maxLength={key === "street" ? 500 : key === "postal_code" ? 30 : key === "province" ? 100 : 200} onChange={value => updateAddress(index, {[key]: value})} onSelect={item => selectAddress(index, key === "street" ? "address" : key as AddressField, item)} />{feedback(fieldId)}
            </div> : input(fieldId, key, address[key], value => updateAddress(index, {[key]: value}))}</div>;
          })}
          <div className="space-y-2"><Label htmlFor={`bp-address-${index}-country`} required>{t("country")}</Label>
            <SiteCountrySelect id={`bp-address-${index}-country`} {...invalid(`bp-address-${index}-country`)} value={address.country_code} scope={geographyScope} disabled={disabled} readOnly={disabled} required onChange={value => updateAddress(index, {country_code: value})} />{feedback(`bp-address-${index}-country`)}
          </div>
          <div className="space-y-2 sm:col-span-2"><Label htmlFor={`bp-address-${index}-additional_info`}>{t("additional_info")}</Label><Textarea id={`bp-address-${index}-additional_info`} {...invalid(`bp-address-${index}-additional_info`)} value={address.additional_info ?? ""} disabled={disabled} onChange={e => updateAddress(index, {additional_info: e.target.value})} />{feedback(`bp-address-${index}-additional_info`)}</div></div>
          <div className="space-y-3"><h4 className="text-sm font-medium">{t("usages")}</h4>{["REGISTERED", "BILLING", "SHIPPING", "CORRESPONDENCE"].map(usage => {
            const selected = address.usages.find(item => item.usage === usage);
            return <div key={usage} className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-muted/40 p-3">
              {checkbox(`bp-address-${index}-${usage}`, usage, Boolean(selected), checked => updateAddress(index, {usages: checked ? [...address.usages, {usage, is_default: false}] : address.usages.filter(item => item.usage !== usage)}))}
              {checkbox(`bp-address-${index}-${usage}-default`, "default", selected?.is_default ?? false, checked => updateAddress(index, {usages: address.usages.map(entry => entry.usage === usage ? {...entry, is_default: checked} : entry)}), !selected)}
            </div>;
          })}</div>
        </fieldset>);}
    const contact = related.row; return (<fieldset key={index} className="space-y-4 rounded-lg border p-4" disabled={disabled}><legend className="px-1 text-sm font-medium">{t("contact")} {index + 1}</legend><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {select(`bp-contact-${index}-type`, "channelType", contact.channel_type, ["EMAIL", "PHONE", "MOBILE", "PEC", "WEBSITE"], value => updateContact(index, {channel_type: value, is_primary: false}))}
          {input(`bp-contact-${index}-value`, "contactValue", contact.value, value => updateContact(index, {value}), ["EMAIL", "PEC"].includes(contact.channel_type) ? "email" : contact.channel_type === "WEBSITE" ? "url" : "tel", true)}
          {input(`bp-contact-${index}-purpose`, "purpose", contact.purpose, value => updateContact(index, {purpose: value}))}
        </div>{checkbox(`bp-contact-${index}-primary`, "primary", contact.is_primary, checked => updateContact(index, {is_primary: checked}))}
        </fieldset>);
  }
  const rowLabel = (kind: RelatedKind, index: number) => {
    const row = kind === "tax" ? draft.tax_identifiers[index] : kind === "address" ? draft.addresses[index] : draft.contact_channels[index];
    return `${t(kind === "tax" ? "taxIdentifier" : kind)} ${index + 1}${row ? ` — ${"value" in row ? row.value : [row.label, row.street, row.city].filter(Boolean).join(", ")}` : ""}`;
  };
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (related || removal || !editable || loading || busy || locked.current || (id && expectedVersion === null)) return;
    const pendingCreate = !id && readState(key)?.draft;
    if (pendingCreate?.id === null && (pendingCreate.createUncertain || pendingCreate.verificationId) && !verificationId && (!recoveryReady || !createUncertain)) return;
    if (verificationId) {
      locked.current = true; setBusy(true); setError("");
      try {await api<PartnerRecord>(scope(`/data/business-partners/${encodeURIComponent(verificationId)}`)); clearRecovery(); onSaved();}
      catch (e) {setError(onError(e));}
      finally {locked.current = false; setBusy(false);}
      return;
    }
    if (createUncertain) return;
    setFieldError(null);
    if (!id && numberingMode === "MANUAL" && !draft.code.trim()) {showError(new ApiError("business_partner_code_required", 400, "values.code")); return;}
    if (draft.status === "ACTIVE" && (draft.kind === "ORGANIZATION" ? !draft.legal_name.trim() : !draft.first_name.trim() || !draft.last_name.trim())) {showError(new ApiError("business_partner_name_required", 400, `values.${draft.kind === "ORGANIZATION" ? "legal_name" : !draft.first_name.trim() ? "first_name" : "last_name"}`)); return;}
    const invalidContact = draft.contact_channels.findIndex(contact => Boolean(contactError(contact)));
    if (invalidContact >= 0) {
      const type = draft.contact_channels[invalidContact].channel_type;
      showError(new ApiError(["EMAIL", "PEC"].includes(type) ? "invalid_contact_email" : ["PHONE", "MOBILE"].includes(type) ? "invalid_contact_phone" : "invalid_contact_website", 400, `contactChannels[${invalidContact}].value`)); return;
    }
    if (!id) {
      if (!writeState(key, {...readState(key), draft: {id, draft, expectedVersion, related, verificationId: null, createUncertain: true}})) {setError(a("createStorageUnavailable")); return;}
      setCreateUncertain(true);
    }
    locked.current = true; setBusy(true); setError("");
    let accepted = false;
    try {
      const record = await api<PartnerRecord>(scope(id ? `/data/business-partners/${encodeURIComponent(id)}/save` : "/data/business-partners/save"), id ? "PUT" : "POST", {
        values: {kind: draft.kind, legal_name: draft.kind === "ORGANIZATION" ? draft.legal_name.trim() || null : null, first_name: draft.kind === "PERSON" ? draft.first_name.trim() || null : null, last_name: draft.kind === "PERSON" ? draft.last_name.trim() || null : null, status: draft.status, ...(!id && numberingMode !== "AUTO" && draft.code.trim() ? {code: draft.code.trim()} : {})},
        ...serializeCollections(draft),
        ...(id ? {expectedVersion} : {}),
      });
      if (!record?.id) throw new Error("Missing saved record id");
      accepted = true;
      setVerificationId(record.id); setCreateUncertain(false);
      writeState(key, {...readState(key), draft: {id, draft, expectedVersion, related, verificationId: record.id, createUncertain: false}});
      await api<PartnerRecord>(scope(`/data/business-partners/${encodeURIComponent(record.id)}`));
      clearRecovery(); onSaved();
    } catch (e) {if (!id && !accepted && e instanceof ApiError && e.status >= 400 && e.status < 500 && e.status !== 408) {setCreateUncertain(false); writeState(key, {...readState(key), draft: {id, draft, expectedVersion, related, verificationId: null, createUncertain: false}});} if (e instanceof ApiError && e.code === "business_partner_code_required") setNumberingMode("MANUAL"); showError(e);}
    finally {locked.current = false; setBusy(false);}
  }
  return <form onSubmit={save} className="space-y-5" aria-busy={loading || busy}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">{id ? a(editable ? "edit" : "details") : t("new")}</h2><Button type="button" variant="outline" disabled={busy || (createUncertain && !verificationId)} onClick={() => {clearRecovery(); onClose();}}>{a(editable ? "cancel" : "close")}</Button></div>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {loading ? <p role="status">{a("loading")}</p> : <Card className="p-4 sm:p-6"><h3 className="font-semibold">{t("identity")}</h3><div className="grid gap-4 sm:grid-cols-2">
      {choice("kind", ["ORGANIZATION", "PERSON"])}{choice("status", ["DRAFT", "ACTIVE", "BLOCKED", "ARCHIVED"])}
      {draft.kind === "ORGANIZATION" ? text("legal_name", draft.status === "ACTIVE") : <>{text("first_name", draft.status === "ACTIVE")}{text("last_name", draft.status === "ACTIVE")}</>}
      {id ? <div><Label>{t("code")}</Label><p className="mt-2 font-mono">{draft.code}</p><p className="text-sm text-muted-foreground">{t("immutableCode")}</p></div> : numberingMode === "AUTO" ? <p className="text-sm text-muted-foreground">{t("automaticCode")}</p> : <div>{text("code", numberingMode === "MANUAL")}<p className="mt-2 text-sm text-muted-foreground">{t(numberingMode === "MANUAL" ? "manualCode" : "codeHint")}</p></div>}
    </div></Card>}
    {!loading && (["tax", "address", "contact"] as const).map(kind => {
      const rows = kind === "tax" ? draft.tax_identifiers : kind === "address" ? draft.addresses : draft.contact_channels;
      const columns = kind === "tax" ? ["country", "identifierType", "identifierValue"] : kind === "address" ? ["label", "address", "country", "usages"] : ["channelType", "contactValue", "purpose", "primary"];
      return <Card key={kind} className="gap-3 p-4 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{t(kind === "tax" ? "taxIdentifiers" : kind === "address" ? "addresses" : "contacts")}</h3>{editable && <Button type="button" variant="outline" size="sm" data-action={`add-${kind}`} disabled={baseDisabled || Boolean(related || removal)} onClick={() => openRelated(kind, rows.length, "add")}><Plus size={16} />{t(kind === "tax" ? "addTax" : kind === "address" ? "addAddress" : "addContact")}</Button>}</div>
        <div className="overflow-x-auto"><Table data-bp-related-table={kind}><colgroup><col span={columns.length} /><col className="w-[120px]" /></colgroup><TableHeader><TableRow>{columns.map(column => <TableHead key={column} kind={column === "primary" ? "status" : "text"}>{t(column)}</TableHead>)}<TableHead kind="actions" data-bp-actions="header" className={actionColumnClassName}>{a("actions")}</TableHead></TableRow></TableHeader><TableBody>
          {!rows.length && <TableRow><TableCell colSpan={columns.length + 1} className="text-muted-foreground">{t(kind === "tax" ? "noTax" : kind === "address" ? "noAddresses" : "noContacts")}</TableCell></TableRow>}
          {rows.map((row, index) => <TableRow key={index}>
            {"identifier_type" in row ? <><TableCell kind="text">{countryLabels.get(row.country_code) ?? countryLabel(row.country_code, locale)}</TableCell><TableCell kind="text">{t(row.identifier_type)}</TableCell><TableCell kind="text" className="max-w-64 truncate">{row.value}</TableCell></> : "street" in row ? <><TableCell kind="text">{row.label || "—"}</TableCell><TableCell kind="text" className="max-w-80 whitespace-normal">{[row.street, row.street_number, row.postal_code, row.city, row.province].filter(Boolean).join(", ")}</TableCell><TableCell kind="text">{countryLabels.get(row.country_code) ?? countryLabel(row.country_code, locale)}</TableCell><TableCell kind="text" className="max-w-64 whitespace-normal">{row.usages.map(entry => `${t(entry.usage)}${entry.is_default ? ` (${t("default")})` : ""}`).join(", ") || "—"}</TableCell></> : <><TableCell kind="text">{t(row.channel_type)}</TableCell><TableCell kind="text" className="max-w-64 truncate">{row.value}</TableCell><TableCell kind="text" className="max-w-48 truncate">{row.purpose || "—"}</TableCell><TableCell kind="status">{row.is_primary ? t("primary") : "—"}</TableCell></>}
            <TableCell kind="actions" data-bp-actions="cell" className={actionColumnClassName}><div className="flex justify-center gap-1">{(["details", "edit", "remove"] as const).filter(operation => operation === "details" || editable).map(operation => {
              const Icon = actionIcons[operation], label = `${a(operation)} ${rowLabel(kind, index)}`;
              return <Button key={operation} type="button" variant="ghost" size="icon" className="size-8 shrink-0" data-action={`${operation}-${kind}-${index}`} aria-label={label} title={label} disabled={loading || busy || Boolean(verificationId || related || removal)} onClick={() => operation === "remove" ? setRemoval({kind, index}) : openRelated(kind, index, operation as "details" | "edit")}><Icon size={16} aria-hidden={true} /></Button>;
            })}</div></TableCell>
          </TableRow>)}
        </TableBody></Table></div>
      </Card>;
    })}
    {!loading && id && companyPartnerReadable(session) && <BusinessPartnerCompanies key={id} businessPartnerId={id} {...{session, scope, onError}} />}
    {related && <Dialog open onOpenChange={open => {if (!open && !busy && !locked.current) {setRelated(null); setFieldError(null);}}}><DialogContent data-bp-related-editor={related.kind} className="sm:max-w-3xl max-h-[90dvh] overflow-y-auto">
      <DialogHeader><DialogTitle>{related.mode === "add" ? a("add") : a(related.mode)} — {rowLabel(related.kind, related.index)}</DialogTitle><DialogDescription>{t(id ? "relatedSaveHint" : "relatedDraftHint")}</DialogDescription></DialogHeader>
      <form data-bp-related-form onSubmit={applyRelated} className="space-y-4">{rowFields()}<DialogFooter><Button type="button" variant="outline" data-action="cancel-related" disabled={busy} onClick={() => {if (!busy && !locked.current) {setRelated(null); setFieldError(null);}}}>{a(related.mode === "details" ? "close" : "cancel")}</Button>{related.mode !== "details" && <Button type="submit" data-action="apply-related" disabled={baseDisabled}>{id ? a("save") : t("applyRelated")}</Button>}</DialogFooter></form>
    </DialogContent></Dialog>}
    {removal && <AlertDialog open onOpenChange={open => {if (!open && !busy && !locked.current) setRemoval(null);}}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{a("remove")} — {rowLabel(removal.kind, removal.index)}</AlertDialogTitle><AlertDialogDescription>{t(id ? "removeRelatedSavedHint" : "removeRelatedHint", {row: rowLabel(removal.kind, removal.index)})}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel type="button" data-action="cancel-remove-related" disabled={busy} onClick={() => {if (!busy && !locked.current) setRemoval(null);}}>{a("cancel")}</AlertDialogCancel><AlertDialogAction type="button" data-action="confirm-remove-related" disabled={baseDisabled} onClick={removeRelated}>{a("remove")}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>}
    {createUncertain && !verificationId && <p role="alert" className="text-sm text-destructive">{a("createUncertain")}</p>}
    {verificationId && <p role="status" className="text-sm text-muted-foreground">{t("verificationHint")}</p>}
    {editable && <div className="sticky bottom-0 z-10 flex justify-end border-t bg-background/95 py-3"><Button type="submit" disabled={loading || busy || Boolean(related || removal) || Boolean(id && expectedVersion === null) || (createUncertain && !verificationId)}>{busy ? a("loading") : verificationId ? t("verifySaved") : a("save")}</Button></div>}
  </form>;
}
