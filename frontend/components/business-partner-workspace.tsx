"use client";
import {useEffect, useMemo, useRef, useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import {Plus, RefreshCw, Pencil} from "lucide-react";
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

type Props = {session: Session; scope: (path: string) => string; onError: (error: unknown) => string};
type Result = {items: Row[]; total: number; page: number; pageSize: number};
export function BusinessPartnerWorkspace({session, scope, onError}: Props) {
  const t = useTranslations("businessPartners"), a = useTranslations("app");
  const readable = can(session, "business-partners", "read");
  const [result, setResult] = useState<Result>({items: [], total: 0, page: 1, pageSize: 25});
  const [search, setSearch] = useState(""), [query, setQuery] = useState(""), [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [editor, setEditor] = useState<{id: string | null} | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {const timer = setTimeout(() => {setQuery(search); setPage(1);}, 300); return () => clearTimeout(timer);}, [search]);
  useEffect(() => {
    let alive = true; const controller = new AbortController();
    if (!readable) {setLoading(false); return;}
    setLoading(true); setError("");
    api<Result>(scope(`/data/business-partners?page=${page}&pageSize=25&search=${encodeURIComponent(query)}`), "GET", undefined, {signal: controller.signal})
      .then(data => {if (alive) {setResult(data); if (!data.items.length && page > 1) setPage(page - 1);}})
      .catch(e => {if (alive) {setResult({items: [], total: 0, page, pageSize: 25}); setError(onError(e));}})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [session, scope, page, query, revision, onError, readable]);
  if (editor) return <BusinessPartnerEditor {...{session, scope, onError}} id={editor.id} onClose={() => setEditor(null)} onSaved={() => {setEditor(null); setSaved(true); setRevision(v => v + 1);}} />;
  return <div className="space-y-4">
    <div className="flex flex-wrap justify-end gap-2">{can(session, "business-partners", "create") && <Button onClick={() => {setSaved(false); setEditor({id: null});}}><Plus size={16} />{t("new")}</Button>}</div>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {saved && <p role="status" className="success">{a("saved")}</p>}
    {readable && <Card className="gap-0 overflow-hidden py-0">
      <div className="table-toolbar"><Input aria-label={t("search")} placeholder={t("search")} value={search} onChange={e => setSearch(e.target.value)} /><span className="shrink-0 text-sm">{result.total} {a("records", {count: result.total})}</span><Button variant="ghost" size="icon" aria-label={a("refresh")} disabled={loading} onClick={() => setRevision(v => v + 1)}><RefreshCw size={16} /></Button></div>
      <div className="table-scroll" aria-busy={loading}><Table><TableHeader><TableRow>{["code", "displayName", "kind", "status"].map(key => <TableHead key={key}>{t(key)}</TableHead>)}<TableHead>{a("actions")}</TableHead></TableRow></TableHeader>
        <TableBody>{!result.items.length ? <TableRow><TableCell colSpan={5}><p className="table-empty" role="status">{loading ? a("loading") : a("empty")}</p></TableCell></TableRow> : result.items.map(row => {
          const name = String(row.legal_name || [row.first_name, row.last_name].filter(Boolean).join(" ") || row.code);
          return <TableRow key={row.id}><TableCell>{String(row.code ?? "—")}</TableCell><TableCell className="min-w-48 whitespace-normal font-medium">{name}</TableCell><TableCell>{t(String(row.kind))}</TableCell><TableCell><Badge variant="secondary">{t(String(row.status))}</Badge></TableCell><TableCell><Button variant="ghost" size="icon" aria-label={`${can(session, "business-partners", "update") ? a("edit") : a("details")} ${name}`} onClick={() => {setSaved(false); setEditor({id: row.id});}}><Pencil size={16} /></Button></TableCell></TableRow>;
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
const emptyDraft = (): PartnerDraft => ({kind: "ORGANIZATION", legal_name: "", first_name: "", last_name: "", status: "DRAFT", code: "", tax_identifiers: [], addresses: [], contact_channels: []});
export function BusinessPartnerEditor({session, scope, onError, id, onClose, onSaved}: Props & {id: string | null; onClose: () => void; onSaved: () => void}) {
  const locale = useLocale();
  const countryOptions = useMemo(() => countryCodes.map(value => ({value, label: countryLabel(value, locale)}))
    .sort((a, b) => a.label.localeCompare(b.label, locale)), [locale]);
  const countryLabels = new Map(countryOptions.map(option => [option.value, option.label]));
  const a = useTranslations("app"), t = useTranslations("businessPartners");
  const [draft, setDraft] = useState<PartnerDraft>(emptyDraft), [expectedVersion, setExpectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(Boolean(id)), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [fieldError, setFieldError] = useState<{id: string; message: string} | null>(null);
  const locked = useRef(false);
  const [numberingMode, setNumberingMode] = useState<"AUTO" | "MANUAL" | null>(null);
  const [verificationId, setVerificationId] = useState<string | null>(null);
  const numberingReadable = can(session, "business-partner-numbering", "read");
  const editable = can(session, "business-partners", id ? "update" : "create"), disabled = !editable || loading || busy || Boolean(verificationId);
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
      .then(record => {if (alive) {setDraft({...emptyDraft(), ...record, legal_name: record.legal_name ?? "", first_name: record.first_name ?? "", last_name: record.last_name ?? ""}); setExpectedVersion(record.version);}})
      .catch(e => {if (alive) setError(onError(e));})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [id, scope, onError]);
  const set = (key: keyof PartnerDraft, value: unknown) => {if (!disabled) {setDraft(current => ({...current, [key]: value})); setError(""); setFieldError(null);}};
  function showError(error: unknown) {
    const message = onError(error), field = error instanceof ApiError ? error.field : undefined;
    let target: {id: string; label: string} | undefined;
    const identity = /^values\.(legal_name|first_name|last_name|kind|status|code)$/.exec(field ?? "");
    if (identity) target = {id: `bp-${identity[1]}`, label: t(identity[1])};
    const tax = /^taxIdentifiers\[(\d+)\]\.(country_code|identifier_type|value|normalized_value)$/.exec(field ?? "");
    if (tax && draft.tax_identifiers[Number(tax[1])]) {
      const row = draft.tax_identifiers[Number(tax[1])];
      const key = tax[2] === "country_code" ? "country" : tax[2] === "identifier_type" ? "type" : "value";
      const label = key === "country" ? "country" : key === "type" ? "identifierType" : ["VAT", "FISCAL_CODE", "FOREIGN_TAX_ID"].includes(row.identifier_type) ? row.identifier_type : "identifierValue";
      target = {id: `bp-tax-${tax[1]}-${key}`, label: `${t("taxIdentifier")} ${Number(tax[1]) + 1} — ${t(label)}`};
    }
    const address = /^addresses\[(\d+)\]\.(label|street|street_number|postal_code|city|province|country_code|additional_info)$/.exec(field ?? "");
    if (address && draft.addresses[Number(address[1])]) {
      const key = address[2] === "country_code" ? "country" : address[2];
      target = {id: `bp-address-${address[1]}-${key}`, label: `${t("address")} ${Number(address[1]) + 1} — ${t(key)}`};
    }
    const usage = /^addresses\[(\d+)\]\.usages\[(\d+)\]\.(usage|is_default)$/.exec(field ?? "");
    if (usage) {
      const row = draft.addresses[Number(usage[1])]?.usages[Number(usage[2])];
      if (row && ["REGISTERED", "BILLING", "SHIPPING", "CORRESPONDENCE"].includes(row.usage)) target = {id: `bp-address-${usage[1]}-${row.usage}${usage[3] === "is_default" ? "-default" : ""}`, label: `${t("address")} ${Number(usage[1]) + 1} — ${t(row.usage)}${usage[3] === "is_default" ? ` — ${t("default")}` : ""}`};
    }
    const contact = /^contactChannels\[(\d+)\]\.(channel_type|value|purpose|is_primary)$/.exec(field ?? "");
    if (contact && draft.contact_channels[Number(contact[1])]) {
      const row = draft.contact_channels[Number(contact[1])];
      const key = contact[2] === "channel_type" ? "type" : contact[2] === "is_primary" ? "primary" : contact[2];
      const label = key === "type" ? "channelType" : key === "value" && ["EMAIL", "PHONE", "MOBILE", "PEC", "WEBSITE"].includes(row.channel_type) ? row.channel_type : key === "value" ? "contactValue" : key;
      target = {id: `bp-contact-${contact[1]}-${key}`, label: `${t("contact")} ${Number(contact[1]) + 1} — ${t(label)}`};
    }
    setError(target ? `${target.label}: ${message}` : message);
    setFieldError(target ? {id: target.id, message} : null);
  }
  const invalid = (fieldId: string) => ({"aria-invalid": fieldError?.id === fieldId || undefined, "aria-describedby": fieldError?.id === fieldId ? `${fieldId}-error` : undefined});
  const feedback = (fieldId: string) => fieldError?.id === fieldId ? <p id={`${fieldId}-error`} className="text-sm text-destructive">{fieldError.message}</p> : null;
  function text(key: "legal_name" | "first_name" | "last_name" | "code", required = false) {
    return <div className="space-y-2"><Label htmlFor={`bp-${key}`}>{t(key)}</Label><Input id={`bp-${key}`} {...invalid(`bp-${key}`)} value={draft[key]} required={required} disabled={disabled} onChange={e => set(key, e.target.value)} />{feedback(`bp-${key}`)}</div>;
  }
  function choice(key: "kind" | "status", options: string[]) {
    return <div className="space-y-2"><Label htmlFor={`bp-${key}`}>{t(key)}</Label><Select value={draft[key]} disabled={disabled} onValueChange={value => set(key, value)}><SelectTrigger id={`bp-${key}`} {...invalid(`bp-${key}`)} className="w-full"><SelectValue /></SelectTrigger><SelectContent>{options.map(option => <SelectItem key={option} value={option}>{t(option)}</SelectItem>)}</SelectContent></Select>{feedback(`bp-${key}`)}</div>;
  }
  function input(fieldId: string, label: string, value: string, onChange: (value: string) => void, type = "text", required = false) {
    return <div className="space-y-2"><Label htmlFor={fieldId}>{t(label)}</Label><Input id={fieldId} {...invalid(fieldId)} type={type} value={value ?? ""} disabled={disabled} required={required} onChange={e => {if (!disabled) onChange(e.target.value);}} />{feedback(fieldId)}</div>;
  }
  function select(fieldId: string, label: string, value: string, options: string[], onChange: (value: string) => void, country = false) {
    const entries = country ? [...countryOptions.map(option => option.value), ...(value && !countryLabels.has(value) ? [value] : [])] : options;
    return <div className="space-y-2"><Label htmlFor={fieldId}>{t(label)}</Label><Select value={value} disabled={disabled} required onValueChange={next => {if (!disabled) onChange(next);}}><SelectTrigger id={fieldId} {...invalid(fieldId)} className="w-full"><SelectValue /></SelectTrigger><SelectContent>{entries.map(option => <SelectItem key={option} value={option}>{country ? countryLabels.get(option) ?? countryLabel(option, locale) : t(option)}</SelectItem>)}</SelectContent></Select>{feedback(fieldId)}</div>;
  }
  const updateTax = (index: number, changes: Partial<TaxIdentifier>) => set("tax_identifiers", draft.tax_identifiers.map((item, i) => i === index ? {...item, ...changes} : item));
  const updateAddress = (index: number, changes: Partial<PartnerAddress>) => set("addresses", draft.addresses.map((item, i) => i === index ? {...item, ...changes} : item));
  const updateContact = (index: number, changes: Partial<ContactChannel>) => set("contact_channels", draft.contact_channels.map((item, i) => i === index ? {...item, ...changes} : item));
  function checkbox(fieldId: string, label: string, checked: boolean, onChange: (checked: boolean) => void, extraDisabled = false) {
    return <div className="space-y-2"><div className="flex items-center gap-2"><Checkbox id={fieldId} {...invalid(fieldId)} checked={checked} disabled={disabled || extraDisabled} onCheckedChange={value => {if (!disabled && !extraDisabled) onChange(value === true);}} /><Label htmlFor={fieldId}>{t(label)}</Label></div>{feedback(fieldId)}</div>;
  }
  function remove(action: string, label: string, index: number, onClick: () => void) {
    return editable && <Button type="button" variant="outline" size="sm" data-action={`remove-${action}-${index}`} aria-label={`${a("remove")} ${t(label)} ${index + 1}`} disabled={disabled} onClick={onClick}>{a("remove")}</Button>;
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!editable || loading || busy || locked.current || (id && expectedVersion === null)) return;
    if (verificationId) {
      locked.current = true; setBusy(true); setError("");
      try {await api<PartnerRecord>(scope(`/data/business-partners/${encodeURIComponent(verificationId)}`)); onSaved();}
      catch (e) {setError(onError(e));}
      finally {locked.current = false; setBusy(false);}
      return;
    }
    setFieldError(null);
    if (!id && numberingMode === "MANUAL" && !draft.code.trim()) {showError(new ApiError("business_partner_code_required", 400, "values.code")); return;}
    if (draft.status === "ACTIVE" && (draft.kind === "ORGANIZATION" ? !draft.legal_name.trim() : !draft.first_name.trim() || !draft.last_name.trim())) {showError(new ApiError("business_partner_name_required", 400, `values.${draft.kind === "ORGANIZATION" ? "legal_name" : !draft.first_name.trim() ? "first_name" : "last_name"}`)); return;}
    const invalidContact = draft.contact_channels.findIndex(contact => {
      const value = contact.value.trim();
      if (["EMAIL", "PEC"].includes(contact.channel_type)) return value.length > 254 || !/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(value);
      if (["PHONE", "MOBILE"].includes(contact.channel_type)) return value.length > 50 || !/[0-9]/.test(value) || !/^[+0-9() .\-/#xXeEtT]+$/.test(value);
      try {const url = new URL(value); return !["http:", "https:"].includes(url.protocol) || !url.hostname || Boolean(url.username || url.password);} catch {return true;}
    });
    if (invalidContact >= 0) {
      const type = draft.contact_channels[invalidContact].channel_type;
      showError(new ApiError(["EMAIL", "PEC"].includes(type) ? "invalid_contact_email" : ["PHONE", "MOBILE"].includes(type) ? "invalid_contact_phone" : "invalid_contact_website", 400, `contactChannels[${invalidContact}].value`)); return;
    }
    locked.current = true; setBusy(true); setError("");
    try {
      const record = await api<PartnerRecord>(scope(id ? `/data/business-partners/${encodeURIComponent(id)}/save` : "/data/business-partners/save"), id ? "PUT" : "POST", {
        values: {kind: draft.kind, legal_name: draft.kind === "ORGANIZATION" ? draft.legal_name.trim() || null : null, first_name: draft.kind === "PERSON" ? draft.first_name.trim() || null : null, last_name: draft.kind === "PERSON" ? draft.last_name.trim() || null : null, status: draft.status, ...(!id && numberingMode !== "AUTO" && draft.code.trim() ? {code: draft.code.trim()} : {})},
        taxIdentifiers: draft.tax_identifiers.map(({country_code, identifier_type, value}) => ({country_code, identifier_type, value})),
        addresses: draft.addresses.map(({label, street, street_number, postal_code, city, province, country_code, additional_info, usages}) => ({label, street, street_number, postal_code, city, province, country_code, additional_info, usages: usages.map(({usage, is_default}) => ({usage, is_default}))})),
        contactChannels: draft.contact_channels.map(({channel_type, value, purpose, is_primary}) => ({channel_type, value, purpose, is_primary})),
        ...(id ? {expectedVersion} : {}),
      });
      setVerificationId(record.id);
      await api<PartnerRecord>(scope(`/data/business-partners/${encodeURIComponent(record.id)}`));
      onSaved();
    } catch (e) {if (e instanceof ApiError && e.code === "business_partner_code_required") setNumberingMode("MANUAL"); showError(e);}
    finally {locked.current = false; setBusy(false);}
  }
  return <form onSubmit={save} className="space-y-5" aria-busy={loading || busy}>
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">{id ? a(editable ? "edit" : "details") : t("new")}</h2><Button type="button" variant="outline" disabled={busy} onClick={onClose}>{a(editable ? "cancel" : "close")}</Button></div>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {loading ? <p role="status">{a("loading")}</p> : <Card className="p-4 sm:p-6"><h3 className="font-semibold">{t("identity")}</h3><div className="grid gap-4 sm:grid-cols-2">
      {choice("kind", ["ORGANIZATION", "PERSON"])}{choice("status", ["DRAFT", "ACTIVE", "BLOCKED", "ARCHIVED"])}
      {draft.kind === "ORGANIZATION" ? text("legal_name", draft.status === "ACTIVE") : <>{text("first_name", draft.status === "ACTIVE")}{text("last_name", draft.status === "ACTIVE")}</>}
      {id ? <div><Label>{t("code")}</Label><p className="mt-2 font-mono">{draft.code}</p><p className="text-sm text-muted-foreground">{t("immutableCode")}</p></div> : numberingMode === "AUTO" ? <p className="text-sm text-muted-foreground">{t("automaticCode")}</p> : <div>{text("code", numberingMode === "MANUAL")}<p className="mt-2 text-sm text-muted-foreground">{t(numberingMode === "MANUAL" ? "manualCode" : "codeHint")}</p></div>}
    </div><p className="text-sm text-muted-foreground">{t("draftHint")}</p></Card>}
    {!loading && <>
      <Card className="p-4 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{t("taxIdentifiers")}</h3>{editable && <Button type="button" variant="outline" size="sm" data-action="add-tax" disabled={disabled} onClick={() => set("tax_identifiers", [...draft.tax_identifiers, {country_code: "IT", identifier_type: "VAT", value: ""}])}><Plus size={16} />{t("addTax")}</Button>}</div>
        {!draft.tax_identifiers.length && <p className="text-sm text-muted-foreground">{t("noTax")}</p>}
        {draft.tax_identifiers.map((tax, index) => <fieldset key={index} className="space-y-4 rounded-lg border p-4" disabled={disabled}><legend className="px-1 text-sm font-medium">{t("taxIdentifier")} {index + 1}</legend><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {select(`bp-tax-${index}-country`, "country", tax.country_code, countryCodes, value => updateTax(index, {country_code: value}), true)}
          {select(`bp-tax-${index}-type`, "identifierType", tax.identifier_type, ["VAT", "FISCAL_CODE", "FOREIGN_TAX_ID"], value => updateTax(index, {identifier_type: value}))}
          {input(`bp-tax-${index}-value`, "identifierValue", tax.value, value => updateTax(index, {value}), "text", true)}
        </div>{remove("tax", "taxIdentifier", index, () => set("tax_identifiers", draft.tax_identifiers.filter((_, i) => i !== index)))}</fieldset>)}
      </Card>
      <Card className="p-4 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{t("addresses")}</h3>{editable && <Button type="button" variant="outline" size="sm" data-action="add-address" disabled={disabled} onClick={() => set("addresses", [...draft.addresses, {label: "", street: "", street_number: "", postal_code: "", city: "", province: "", country_code: "IT", additional_info: "", usages: []}])}><Plus size={16} />{t("addAddress")}</Button>}</div>
        {!draft.addresses.length && <p className="text-sm text-muted-foreground">{t("noAddresses")}</p>}
        {draft.addresses.map((address, index) => <fieldset key={index} className="space-y-4 rounded-lg border p-4" disabled={disabled}><legend className="px-1 text-sm font-medium">{t("address")} {index + 1}</legend>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{(["label", "street", "street_number", "postal_code", "city", "province"] as const).map(key => <div key={key}>{input(`bp-address-${index}-${key}`, key, address[key], value => updateAddress(index, {[key]: value}), "text", ["street", "postal_code", "city"].includes(key))}</div>)}
          {select(`bp-address-${index}-country`, "country", address.country_code, countryCodes, value => updateAddress(index, {country_code: value}), true)}
          <div className="space-y-2 sm:col-span-2"><Label htmlFor={`bp-address-${index}-additional_info`}>{t("additional_info")}</Label><Textarea id={`bp-address-${index}-additional_info`} {...invalid(`bp-address-${index}-additional_info`)} value={address.additional_info ?? ""} disabled={disabled} onChange={e => updateAddress(index, {additional_info: e.target.value})} />{feedback(`bp-address-${index}-additional_info`)}</div></div>
          <div className="space-y-3"><h4 className="text-sm font-medium">{t("usages")}</h4>{["REGISTERED", "BILLING", "SHIPPING", "CORRESPONDENCE"].map(usage => {
            const selected = address.usages.find(item => item.usage === usage);
            return <div key={usage} className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-muted/40 p-3">
              {checkbox(`bp-address-${index}-${usage}`, usage, Boolean(selected), checked => updateAddress(index, {usages: checked ? [...address.usages, {usage, is_default: false}] : address.usages.filter(item => item.usage !== usage)}))}
              {checkbox(`bp-address-${index}-${usage}-default`, "default", selected?.is_default ?? false, checked => set("addresses", draft.addresses.map((item, i) => ({...item, usages: item.usages.map(entry => entry.usage === usage ? {...entry, is_default: i === index ? checked : checked ? false : entry.is_default} : entry)}))), !selected)}
            </div>;
          })}</div>{remove("address", "address", index, () => set("addresses", draft.addresses.filter((_, i) => i !== index)))}
        </fieldset>)}
      </Card>
      <Card className="p-4 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{t("contacts")}</h3>{editable && <Button type="button" variant="outline" size="sm" data-action="add-contact" disabled={disabled} onClick={() => set("contact_channels", [...draft.contact_channels, {channel_type: "EMAIL", value: "", purpose: "", is_primary: false}])}><Plus size={16} />{t("addContact")}</Button>}</div>
        {!draft.contact_channels.length && <p className="text-sm text-muted-foreground">{t("noContacts")}</p>}
        {draft.contact_channels.map((contact, index) => <fieldset key={index} className="space-y-4 rounded-lg border p-4" disabled={disabled}><legend className="px-1 text-sm font-medium">{t("contact")} {index + 1}</legend><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {select(`bp-contact-${index}-type`, "channelType", contact.channel_type, ["EMAIL", "PHONE", "MOBILE", "PEC", "WEBSITE"], value => updateContact(index, {channel_type: value, is_primary: false}))}
          {input(`bp-contact-${index}-value`, "contactValue", contact.value, value => updateContact(index, {value}), ["EMAIL", "PEC"].includes(contact.channel_type) ? "email" : contact.channel_type === "WEBSITE" ? "url" : "tel", true)}
          {input(`bp-contact-${index}-purpose`, "purpose", contact.purpose, value => updateContact(index, {purpose: value}))}
        </div>{checkbox(`bp-contact-${index}-primary`, "primary", contact.is_primary, checked => set("contact_channels", draft.contact_channels.map((item, i) => i === index ? {...item, is_primary: checked} : checked && item.channel_type === contact.channel_type ? {...item, is_primary: false} : item)))}
        {remove("contact", "contact", index, () => set("contact_channels", draft.contact_channels.filter((_, i) => i !== index)))}</fieldset>)}
      </Card>
    </>}
    {verificationId && <p role="status" className="text-sm text-muted-foreground">{t("verificationHint")}</p>}
    {editable && <div className="sticky bottom-0 z-10 flex justify-end border-t bg-background/95 py-3"><Button type="submit" disabled={loading || busy || Boolean(id && expectedVersion === null)}>{busy ? a("loading") : verificationId ? t("verifySaved") : a("save")}</Button></div>}
  </form>;
}
