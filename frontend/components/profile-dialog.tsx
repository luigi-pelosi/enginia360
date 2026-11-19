"use client";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api, refreshCsrf } from "@/lib/api";
import { passwordValidation } from "@/lib/password";
import type { Session } from "@/lib/model";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";

const profileFields = ["first_name", "last_name", "email", "date_of_birth", "phone_number", "preferred_language"] as const;
type ProfileField = typeof profileFields[number];
export type OwnProfile = {id: string; username: string} & Record<ProfileField, string | null>;
type Draft = Record<ProfileField, string>;
function draftOf(profile: OwnProfile): Draft {
  return Object.fromEntries(profileFields.map(name => [name, profile[name] ?? ""])) as Draft;
}

export function ProfileDialog({onClose, onSaved, onError, session}: {
  session?: Session;
  onClose: () => void;
  onSaved: (session: Session) => void;
  onError: (error: unknown) => string;
}) {
  const locale = useLocale();
  const t = useTranslations("app"), f = useTranslations("fields"), languages = useTranslations("languages");
  const [profile, setProfile] = useState<OwnProfile | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [committed, setCommitted] = useState(false);
  const commit = useRef<{profile: OwnProfile; passwordChanged: boolean} | null>(null);
  const inFlight = useRef(false);
  const latestDraft = useRef<Draft | null>(null);
  const tenant = session?.selectedTenantId || session?.tenantId;
  const storageKey = session?.id && tenant ? `profile-draft:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}` : null;
  function clearDraft() { try { if (storageKey) sessionStorage.removeItem(storageKey); } catch { /* Storage is optional. */ } }
  useEffect(() => {
    let alive = true;
    api<OwnProfile>("/profile").then(value => {
      if (alive) {
        const fresh = draftOf(value);
        if (storageKey && value.id === session?.id) try {
          const stored = JSON.parse(sessionStorage.getItem(storageKey) || "null");
          for (const name of profileFields) {
            if (typeof stored?.base?.[name] === "string" && typeof stored?.values?.[name] === "string" && stored.base[name] === fresh[name]) fresh[name] = stored.values[name];
          }
        } catch { /* Ignore unavailable or invalid storage. */ }
        latestDraft.current = fresh;
        setProfile(value); setDraft(fresh);
      }
    }).catch(e => { if (alive) setError(onError(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [onError, storageKey, session?.id]);
  const values = Object.fromEntries(profileFields.filter(name => draft && profile && draft[name] !== (profile[name] ?? ""))
    .map(name => [name, draft![name] || null]));
  const hasValues = Object.keys(values).length > 0;
  const hasPassword = !!(newPassword || confirmPassword);
  const passwordIssue = hasPassword ? (!currentPassword ? "passwordCurrentRequired" :
    passwordValidation(newPassword, confirmPassword) || (newPassword === currentPassword ? "passwordDifferent" : "")) : "";
  const validDate = !draft?.date_of_birth || (/^\d{4}-\d{2}-\d{2}$/.test(draft.date_of_birth)
    && !Number.isNaN(Date.parse(`${draft.date_of_birth}T00:00:00Z`))
    && new Date(`${draft.date_of_birth}T00:00:00Z`).toISOString().slice(0, 10) === draft.date_of_birth
    && draft.date_of_birth <= new Date().toISOString().slice(0, 10));
  const validPersonal = !!draft && !!draft.first_name.trim() && draft.first_name.length <= 200
    && !!draft.last_name.trim() && draft.last_name.length <= 200
    && draft.email.length <= 254 && /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/.test(draft.email.trim())
    && draft.phone_number.length <= 50 && ["it", "en"].includes(draft.preferred_language) && validDate;
  const changed = hasValues || hasPassword;
  const valid = validPersonal && !passwordIssue;
  const locked = loading || busy || committed;
  function close() { if (!inFlight.current) { clearDraft(); onClose(); } }
  function change(name: ProfileField, value: string) {
    if (!inFlight.current && !commit.current && latestDraft.current && profile) {
      const next = {...latestDraft.current, [name]: value};
      latestDraft.current = next;
      setDraft(next);
      if (storageKey && profile.id === session?.id) try {
        const base = draftOf(profile);
        const changedFields = profileFields.filter(field => next[field] !== base[field]);
        if (changedFields.length) sessionStorage.setItem(storageKey, JSON.stringify({
          base: Object.fromEntries(changedFields.map(field => [field, base[field]])),
          values: Object.fromEntries(changedFields.map(field => [field, next[field]])),
        }));
        else clearDraft();
      } catch { /* Storage is optional. */ }
    }
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current || loading || !profile || !draft || (!commit.current && (!changed || !valid))) return;
    inFlight.current = true;
    setBusy(true); setError("");
    try {
      // Dopo il commit ritenta soltanto la lettura di sessione e CSRF:
      // un errore successivo non deve ripetere il cambio password.
      if (!commit.current) {
        const saved = await api<OwnProfile>("/profile", "PUT", {
          ...(hasValues ? {values} : {}),
          ...(hasPassword ? {currentPassword, newPassword} : {}),
        });
        commit.current = {profile: saved, passwordChanged: hasPassword};
        clearDraft();
        setCommitted(true);
      }
      const saved = commit.current.profile;
      if (commit.current.passwordChanged) await refreshCsrf();
      const fresh = await api<Session>("/session");
      onSaved(fresh);
      onClose();
      document.cookie = `locale=${saved.preferred_language}; Path=/; Max-Age=31536000; SameSite=Strict`;
      if (saved.preferred_language !== locale) location.reload();
    } catch (e) { setError(onError(e)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open) close(); }}>
    <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-xl" aria-describedby={undefined}>
      <DialogHeader><DialogTitle>{t("personalProfile")}</DialogTitle></DialogHeader>
      <form id="personal-profile-form" onSubmit={submit} className="grid gap-5" aria-busy={locked}>
        {error && <Alert variant="destructive"><AlertDescription role="alert">{error}</AlertDescription></Alert>}
        {loading ? <p role="status">{t("loading")}</p> : draft && profile && <section className="grid gap-4 sm:grid-cols-2" aria-labelledby="profile-details-heading">
          <h2 id="profile-details-heading" className="font-medium sm:col-span-2">{t("personalDetails")}</h2>
          <div className="field sm:col-span-2"><Label htmlFor="profile-username">{f("username")}</Label><Input id="profile-username" value={profile.username} readOnly /></div>
          {profileFields.map(name => <div className="field" key={name}>
            <Label htmlFor={`profile-${name}`}>{f(name)}</Label>
            {name === "preferred_language" ? <Select value={draft[name]} disabled={locked} onValueChange={value => change(name, value)}>
              <SelectTrigger id={`profile-${name}`}><SelectValue /></SelectTrigger>
              <SelectContent>{(["it", "en"] as const).map(language => <SelectItem key={language} value={language}>{languages(language)}</SelectItem>)}</SelectContent>
            </Select> : <Input id={`profile-${name}`} value={draft[name]} disabled={locked}
              type={name === "email" ? "email" : name === "date_of_birth" ? "date" : name === "phone_number" ? "tel" : "text"}
              required={["first_name", "last_name", "email"].includes(name)}
              max={name === "date_of_birth" ? new Date().toISOString().slice(0, 10) : undefined}
              maxLength={name === "email" ? 254 : name === "phone_number" ? 50 : 200}
              onChange={event => change(name, event.target.value)} />}
          </div>)}
        </section>}
        {draft && profile && <section className="grid gap-4 border-t pt-4" aria-labelledby="profile-password-heading">
          <h2 id="profile-password-heading" className="font-medium">{t("changePassword")} <span className="text-sm font-normal text-muted-foreground">({t("optional")})</span></h2>
          {(["current", "new", "confirm"] as const).map(name => <div className="field" key={name}>
            <Label htmlFor={`profile-password-${name}`}>{t(name === "current" ? "currentPassword" : name === "new" ? "newPassword" : "confirmPassword")}</Label>
            <Input id={`profile-password-${name}`} type="password" autoComplete={name === "current" ? "current-password" : "new-password"}
              value={name === "current" ? currentPassword : name === "new" ? newPassword : confirmPassword} disabled={locked} required={hasPassword}
              aria-invalid={!!passwordIssue} onChange={event => {
                if (!inFlight.current && !commit.current) (name === "current" ? setCurrentPassword : name === "new" ? setNewPassword : setConfirmPassword)(event.target.value);
              }} />
          </div>)}
          {passwordIssue && <p role="alert" className="text-sm text-destructive">{t(passwordIssue)}</p>}
        </section>}
        <DialogFooter>
          <Button id="profile-cancel" type="button" variant="outline" disabled={busy} onClick={close}>{t("cancel")}</Button>
          <Button type="submit" disabled={loading || busy || (!committed && (!changed || !valid))}>{busy ? t("loading") : t("save")}</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}
