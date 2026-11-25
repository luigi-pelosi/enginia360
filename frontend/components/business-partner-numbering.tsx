"use client";
import {useEffect, useRef, useState} from "react";
import {useTranslations} from "next-intl";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Alert, AlertDescription} from "@/components/ui/alert";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {api, ApiError} from "@/lib/api";
import {can, type Session} from "@/lib/model";
export type PartnerNumbering = {mode: "AUTO" | "MANUAL"; prefix: string; padding: number; nextNumber: number; version: number};
function recoveryKey(session: Session, tenantId?: string | null) {
  const tenant = session.isSuperAdmin ? tenantId : session.tenantId;
  return session.id && tenant ? `bp-refresh:v1:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}:numbering` : null;
}
function readRecovery(key: string | null): PartnerNumbering | null {
  try {
    const value = key ? JSON.parse(sessionStorage.getItem(key) || "null") : null;
    return value && (value.mode === "AUTO" || value.mode === "MANUAL") && typeof value.prefix === "string" && typeof value.padding === "number" && typeof value.nextNumber === "number" && Number.isSafeInteger(value.version) && value.version >= 0
      ? {mode: value.mode, prefix: value.prefix, padding: value.padding, nextNumber: value.nextNumber, version: value.version} : null;
  } catch {return null;}
}
function writeRecovery(key: string | null, value: PartnerNumbering | null) {
  try {if (key) {if (value) sessionStorage.setItem(key, JSON.stringify(value)); else sessionStorage.removeItem(key);}} catch { /* Storage may be unavailable. */ }
}
export function resetBusinessPartnerNumberingRecovery(session: Session, tenantId?: string | null) {
  writeRecovery(recoveryKey(session, tenantId), null);
}
export function BusinessPartnerNumbering({session, scope, onError, tenantId}: {session: Session; scope: (path: string) => string; onError: (error: unknown) => string; tenantId?: string | null}) {
  const t = useTranslations("partnerNumbering"), a = useTranslations("app"), errors = useTranslations("errors");
  const [config, setConfig] = useState<PartnerNumbering | null>(null), [baseline, setBaseline] = useState<PartnerNumbering | null>(null);
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState(false), [revision, setRevision] = useState(0), [frozen, setFrozen] = useState(false);
  const lock = useRef(false);
  const readable = can(session, "business-partner-numbering", "read"), editable = readable && can(session, "business-partner-numbering", "update");
  const key = recoveryKey(session, tenantId);
  const disabled = !editable || loading || busy || frozen;
  useEffect(() => {
    if (!readable) {setLoading(false); return;}
    let alive = true; const controller = new AbortController();
    setLoading(true); setError(""); setSaved(false);
    api<PartnerNumbering>(scope("/business-partner-numbering"), "GET", undefined, {signal: controller.signal})
      .then(data => {if (alive) {setConfig(editable ? readRecovery(key) ?? data : data); setBaseline(data);}})
      .catch(e => {if (alive) {setConfig(null); setError(onError(e));}})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false; controller.abort();};
  }, [scope, onError, readable, editable, key, revision]);
  function change(field: keyof PartnerNumbering, value: string | number) {if (!disabled && config) {const next = {...config, [field]: value}; writeRecovery(key, next); setConfig(next); setSaved(false);}}
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!config || disabled || lock.current) return;
    if (!Number.isSafeInteger(config.padding) || config.padding < 1 || config.padding > 15 || !Number.isSafeInteger(config.nextNumber) || config.nextNumber < 1 || config.nextNumber > 1000000000000000 || config.prefix.length > 32 || !/^[\x20-\x7e]*$/.test(config.prefix)) {setError(errors("validation_error")); return;}
    lock.current = true; setBusy(true); setError(""); setSaved(false);
    try {
      const result = await api<PartnerNumbering>(scope("/business-partner-numbering"), "PUT", {mode: config.mode, prefix: config.prefix, padding: config.padding, nextNumber: config.nextNumber, version: config.version});
      // Conserva la revisione restituita anche se la verifica successiva fallisce.
      writeRecovery(key, null);
      setConfig(result); setBaseline(result);
      const fresh = await api<PartnerNumbering>(scope("/business-partner-numbering"));
      setConfig(fresh); setBaseline(fresh); setSaved(true);
    } catch (e) {if (e instanceof ApiError && e.code === "numbering_in_use") setFrozen(true); setError(onError(e));}
    finally {lock.current = false; setBusy(false);}
  }
  return <Card className="max-w-3xl p-4 sm:p-6">
    <p className="text-sm text-muted-foreground">{t("scopeHint")}</p><p className="text-sm text-muted-foreground">{t("freezeHint")}</p>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {saved && <p role="status" className="success">{a("saved")}</p>}
    {loading ? <p role="status">{a("loading")}</p> : config && readable ? <form onSubmit={save} className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2"><Label htmlFor="bp-numbering-mode" required>{t("mode")}</Label><Select value={config.mode} disabled={disabled} onValueChange={value => change("mode", value)}><SelectTrigger id="bp-numbering-mode" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="AUTO">{t("AUTO")}</SelectItem><SelectItem value="MANUAL">{t("MANUAL")}</SelectItem></SelectContent></Select></div>
        <div className="space-y-2"><Label htmlFor="bp-numbering-prefix">{t("prefix")}</Label><Input id="bp-numbering-prefix" maxLength={32} value={config.prefix} disabled={disabled || config.mode === "MANUAL"} onChange={e => change("prefix", e.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="bp-numbering-padding" required>{t("padding")}</Label><Input id="bp-numbering-padding" type="number" min={1} max={15} step={1} required value={config.padding} disabled={disabled || config.mode === "MANUAL"} onChange={e => change("padding", Number(e.target.value))} /></div>
        <div className="space-y-2"><Label htmlFor="bp-numbering-nextNumber" required>{t("nextNumber")}</Label><Input id="bp-numbering-nextNumber" type="number" min={1} max={1000000000000000} step={1} required value={config.nextNumber} disabled={disabled || config.mode === "MANUAL"} onChange={e => change("nextNumber", Number(e.target.value))} /></div>
      </div>
      <div className="rounded-md bg-muted p-4"><span className="block text-sm text-muted-foreground">{t("preview")}</span><output className="break-all font-mono">{config.mode === "MANUAL" ? t("manualHint") : config.prefix + String(config.nextNumber).padStart(Math.min(15, Math.max(1, config.padding || 1)), "0")}</output></div>
      {editable && <div className="flex flex-wrap justify-end gap-2"><Button type="button" variant="outline" disabled={busy || loading} onClick={() => {writeRecovery(key, null); setConfig(baseline); setError(""); setSaved(false);}}>{a("cancel")}</Button><Button type="submit" disabled={disabled}>{busy ? a("loading") : a("save")}</Button></div>}
    </form> : null}
    {readable && <div><Button type="button" variant="outline" disabled={busy || loading} onClick={() => {writeRecovery(key, null); setRevision(v => v + 1);}}>{t("reload")}</Button></div>}
  </Card>;
}
