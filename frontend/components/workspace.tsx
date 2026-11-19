"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { DropdownMenu } from "radix-ui";
import {
  Building2,
  Globe2,
  MapPin,
  Warehouse,
  Boxes,
  Settings,
  Users,
  UsersRound,
  ShieldCheck,
  KeyRound,
  Network,
  Search,
  Plus,
  Pencil,
  Trash2,
  ChevronLeft,
  ChevronRight,
  LogOut,
  UserRound,
  ArrowRight,
  RefreshCw,
  Check,
} from "lucide-react";
import { Sidebar, SidebarContent, SidebarGroup, SidebarGroupLabel, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { ProfileDialog } from "@/components/profile-dialog";
import { BusinessPartnerWorkspace, clearBusinessPartnerRecoveries, resetBusinessPartnerRecovery } from "@/components/business-partner-workspace";
import { BusinessPartnerNumbering, resetBusinessPartnerNumberingRecovery } from "@/components/business-partner-numbering";
import { AddressAutocomplete, addressSelection, type AddressField } from "@/components/address-autocomplete";
import { SiteCountrySelect } from "@/components/site-country-select";
import { PermissionTree } from "@/components/permission-tree";
import { PurchasingCoverageEditor, coverageChanged, coverageValid, type CoverageDraft, type CoverageEntry } from "@/components/purchasing-coverage-editor";
import { RoleCompanyAccess } from "@/components/role-company-access";
import { api, ApiError, refreshCsrf } from "@/lib/api";
import { passwordValidation } from "@/lib/password";
import it from "../messages/it.json";
import en from "../messages/en.json";
import {
  can,
  permissionLabel,
  permissionMatches,
  navigationSections as sections,
  settingsCatalogs,
  partnerSettingsParents,
  canRelation,
  relations,
  relationOptions,
  normalizeValues,
  formatFieldValue,
  countryLabel,
  tableFields,
  siteAddress,
  rowLabel,
  type Session,
  type Resource,
  type Row,
} from "@/lib/model";

const icons: Record<string, typeof Building2> = {
  tenants: Network,
  companies: Building2,
  sites: MapPin,
  "sales-organizations": Building2,
  "purchasing-organizations": Building2,
  "warehouse-types": Boxes,
  warehouses: Warehouse,
  "warehouse-locations": Boxes,
  settings: Settings,
  "business-partners": UsersRound,
  "business-partner-numbering": Settings,
  countries: Globe2,
  cities: MapPin,
  users: Users,
  groups: UsersRound,
  roles: ShieldCheck,
  permissions: KeyRound,
};
function canOpenResource(session: Session, key: string) {
  if (key in partnerSettingsParents) return can(session, "business-partner-numbering", "read");
  return key === "settings" || can(session, key, "read");
}
/* workspace-navigation-helpers */
function workspaceRoute(search: string, allowed: string[]): string {
  const values = new URLSearchParams(search).getAll("view");
  return values.length === 1 && allowed.includes(values[0]) ? values[0] : "";
}
function workspaceTenantKey(session: {id: string}): string {
  return `workspace-tenant:${encodeURIComponent(session.id)}`;
}
function workspaceTenant(session: Session, available: Row[]): string {
  if (!session.isSuperAdmin) return session.tenantId || "";
  let selected = session.selectedTenantId || "";
  try { selected = sessionStorage.getItem(workspaceTenantKey(session)) ?? selected; }
  catch { /* La selezione del login resta disponibile senza storage. */ }
  return !selected || available.some(row => row.id === selected) ? selected : "";
}
function rememberWorkspaceTenant(session: Session, tenant: string) {
  if (!session.isSuperAdmin) return;
  try { sessionStorage.setItem(workspaceTenantKey(session), tenant); }
  catch { /* La selezione resta utilizzabile nella pagina corrente. */ }
}
/* end-workspace-navigation-helpers */

/* profile-recovery-helpers */
function profileRecoveryKey(session: {id: string}, tenant: string) {
  return session.id && tenant ? `profile-open:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}` : null;
}
function clearProfileRecovery(session: {id: string}, tenant: string) {
  const key = profileRecoveryKey(session, tenant);
  if (!key) return;
  try {
    sessionStorage.removeItem(key);
    sessionStorage.removeItem(`profile-draft:${encodeURIComponent(session.id)}:${encodeURIComponent(tenant)}`);
  } catch { /* Storage is optional. */ }
}
function clearUserProfileRecoveries(session: {id: string}) {
  try {
    const id = encodeURIComponent(session.id);
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const key = sessionStorage.key(i);
      if (key?.startsWith(`profile-open:${id}:`) || key?.startsWith(`profile-draft:${id}:`)) sessionStorage.removeItem(key);
    }
  } catch { /* Storage is optional. */ }
}
/* end-profile-recovery-helpers */
/* record-recovery-helpers */
function recoverableValues(fields: {name: string; type: string}[], values: Record<string, unknown>) {
  return Object.fromEntries(fields.filter(field => field.type !== "json" && field.type !== "password" && !/(password|secret|token|api.?key|credential)/i.test(field.name)).filter(field => Object.hasOwn(values, field.name)).map(field => [field.name, values[field.name]]));
}
/* end-record-recovery-helpers */
function recordRecoveryKey(session: Session, tenant: string, resource: string) {return `workspace:${session.id}:${tenant}:record:${resource}`;}
function recordPendingKey(session: Session, tenant: string, resource: string) {return `record-pending:${session.id}:${tenant}:${resource}`;}
function clearRecordRecovery(session: Session, tenant: string, resource: string) {
  try {
    if (!sessionStorage.getItem(recordPendingKey(session, tenant, resource))) sessionStorage.removeItem(recordRecoveryKey(session, tenant, resource));
  } catch { /* Preserve recovery if storage is unavailable. */ }
}
type Result = { items: Row[]; total: number; page: number; pageSize: number };
const permissionMessages = [it, en];
function localizedRowLabel(resource: string, row: Row, locale: string) {
  return resource === "permissions" ? permissionLabel(row, locale === "en" ? en : it) : rowLabel(row);
}

function classificationOptionLabel(name: string, option: string, locale: string) {
  const labels: Record<string, Record<string, string>> = (locale === "en" ? en : it).fieldOptions;
  return labels[name]?.[option] ?? "—";
}

function Brand({ className = "h-7 w-auto max-w-full object-contain object-left" }: { className?: string } = {}) {
  return <img src="/enginia360-logo.png" alt="Enginia360" className={className} />;
}
function LocaleControl() {
  const t = useTranslations("app");
  const locale = useLocale();
  return <Select value={locale} onValueChange={(value) => {
    document.cookie = `locale=${value}; Path=/; Max-Age=31536000; SameSite=Strict`;
    location.reload();
  }}>
    <SelectTrigger aria-label={t("language")} className="w-28"><SelectValue /></SelectTrigger>
    <SelectContent><SelectItem value="it">Italiano</SelectItem><SelectItem value="en">English</SelectItem></SelectContent>
  </Select>;
}
function WorkspaceNavigation({accessible, active, navigate, session}: {accessible: Resource[]; active: string; navigate: (key: string) => void; session: Session}) {
  const t = useTranslations("app"), r = useTranslations("resources");
  const {setOpenMobile} = useSidebar();
  return <Sidebar>
    <SidebarHeader className="p-4"><Brand className="h-auto w-full object-contain" /><span className="text-xs text-muted-foreground">{session.isSuperAdmin ? t("platform") : t("workspace")}</span></SidebarHeader>
    <SidebarContent><nav aria-label={t("menu")}>
      {sections.map(section => {
        const keys = section.keys.filter(key => accessible.some(x => x.key === key));
        return keys.length ? <SidebarGroup key={section.label}>
          <SidebarGroupLabel>{t(section.label)}</SidebarGroupLabel>
          <SidebarMenu>{keys.map(key => {
            const Icon = icons[key] || Boxes;
            const selected = key === active || key === "settings" && (settingsCatalogs.includes(active) || active in partnerSettingsParents);
            return <SidebarMenuItem key={key}><SidebarMenuButton isActive={selected} aria-current={selected ? "page" : undefined} onClick={() => {navigate(key); setOpenMobile(false)}}><Icon /><span>{r(key)}</span></SidebarMenuButton></SidebarMenuItem>;
          })}</SidebarMenu>
        </SidebarGroup> : null;
      })}
    </nav></SidebarContent>
  </Sidebar>;
}
function Notice({ message }: { message: string }) {
  return message ? (
    <Alert variant="destructive" className="mb-4"><AlertDescription>{message}</AlertDescription></Alert>
  ) : null;
}
export default function Workspace() {
  const locale = useLocale();
  const languages = useTranslations("languages");
  const t = useTranslations("app"),
    r = useTranslations("resources"),
    f = useTranslations("fields"),
    err = useTranslations("errors");
  const [session, setSession] = useState<Session | null>(null),
    [initial, setInitial] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [resources, setResources] = useState<Resource[]>([]),
    [active, setActive] = useState(""),
    [tenant, setTenant] = useState(""),
    [tenants, setTenants] = useState<Row[]>([]);
  const [rows, setRows] = useState<Row[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [loading, setLoading] = useState(false),
    [version, setVersion] = useState(0);
  const [editor, setEditor] = useState<{
      resource: Resource;
      row: Row | null;
    } | null>(null),
    [deleting, setDeleting] = useState<Row | null>(null),
    [profileOpen, setProfileOpen] = useState(false),
    [resetUser, setResetUser] = useState<Row | null>(null);
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [tenantCode, setTenantCode] = useState("");
  const [partnerWorkspaceVersion, setPartnerWorkspaceVersion] = useState(0);
  const [workspaceVersion, setWorkspaceVersion] = useState(0);
  const [navigationReady, setNavigationReady] = useState(false);
  const restoredNavigation = useRef(false);
  useEffect(() => {
    if (initial || !session || session.mustChangePassword || !tenant) { setProfileOpen(false); return; }
    const key = profileRecoveryKey(session, tenant);
    try { setProfileOpen(!!key && sessionStorage.getItem(key) === "1"); }
    catch { setProfileOpen(false); }
  }, [initial, session?.id, session?.mustChangePassword, tenant]);
  const translateError = useCallback(
    (e: unknown) => {
      const code = e instanceof ApiError ? e.code : "server_error";
      if (code === "password_change_required")
        setSession((s) => (s ? { ...s, mustChangePassword: true } : s));
      if (e instanceof ApiError && e.status === 401) setSession(null);
      return err.has(code) ? err(code) : err("server_error");
    },
    [err],
  );
  const scope = useCallback(
    (path: string) =>
      /^\/data\/(tenants|countries|cities)(?:[/?]|$)/.test(path) ? path :
      `${path}${path.includes("?") ? "&" : "?"}${tenant ? `tenantId=${encodeURIComponent(tenant)}` : ""}`,
    [tenant],
  );
  const allRows = useCallback(
    async (key: string): Promise<Row[]> => {
      let result: Row[] = [];
      for (let p = 1; p <= 1000; p++) {
        const data = await api<Result>(
          scope(`/data/${key}?page=${p}&pageSize=100`),
        );
        result = result.concat(data.items);
        if (result.length >= data.total || !data.items.length) return result;
      }
      throw new ApiError("server_error", 500);
    },
    [scope, version],
  );
  const loadTenants = useCallback(async () => {
    let result: Row[] = [];
    for (let p = 1; p <= 1000; p++) {
      const data = await api<Result>(`/data/tenants?page=${p}&pageSize=100`);
      result = result.concat(data.items);
      if (result.length >= data.total || !data.items.length) break;
    }
    setTenants(result);
    return result;
  }, []);
  const prepareSession = useCallback(async (s: Session): Promise<Session> => {
    if (!s.isSuperAdmin || s.mustChangePassword) return s;
    const available = await loadTenants();
    return {...s, selectedTenantId: workspaceTenant(s, available)};
  }, [loadTenants]);
  useEffect(() => {
    let mounted = true;
    api<Session>("/session")
      .then(prepareSession)
      .then((s) => {
        if (mounted) {
          setSession(s);
          setTenant(s.selectedTenantId ?? s.tenantId ?? "");
        }
      })
      .catch((e) => {
        if (mounted && (!(e instanceof ApiError) || e.status !== 401))
          setError(translateError(e));
      })
      .finally(() => {
        if (mounted) setInitial(false);
      });
    return () => {
      mounted = false;
    };
  }, [translateError, prepareSession]);
  useEffect(() => {
    if (!initial && session && !session.mustChangePassword) rememberWorkspaceTenant(session, tenant);
  }, [initial, session?.id, session?.isSuperAdmin, session?.mustChangePassword, tenant]);
  useEffect(() => {
    if (!session || session.mustChangePassword) return;
    let alive = true;
    api<Resource[]>("/resources")
      .then((data) => {
        if (!alive) return;
        setResources(data);
        const allowed = [...data.map(item => item.key), ...Object.keys(partnerSettingsParents)].filter(key => canOpenResource(session, key));
        const requested = typeof window === "undefined" ? "" : workspaceRoute(window.location.search, allowed);
        const fallback = data.find(x => !settingsCatalogs.includes(x.key) && canOpenResource(session, x.key))?.key || "";
        if (!restoredNavigation.current && typeof window !== "undefined") {
          const route = requested || fallback;
          try {
            const stored = JSON.parse(sessionStorage.getItem(`workspace:${session.id}:${session.selectedTenantId || session.tenantId || ""}:${route}`) || "null");
            if (stored && typeof stored.search === "string" && Number.isSafeInteger(stored.page) && stored.page > 0) {
              setSearch(stored.search); setQuery(stored.search); setPage(stored.page);
            }
          } catch { /* Storage can be unavailable or contain invalid data. */ }
          restoredNavigation.current = true;
          setNavigationReady(true);
        }
        setActive((current) =>
          (current in partnerSettingsParents && canOpenResource(session, current)) || data.some((x) => x.key === current && canOpenResource(session, x.key))
            ? current
            : requested || fallback,
        );
      })
      .catch((e) => setError(translateError(e)));
    if (session.isSuperAdmin)
      loadTenants().catch((e) => setError(translateError(e)));
    return () => {
      alive = false;
    };
  }, [session, loadTenants, translateError]);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (!session || session.mustChangePassword || !active) return;
    if (["settings", "business-partners"].includes(active) || active in partnerSettingsParents) {setRows([]); setTotal(0); setLoading(false); return;}
    if (session.isSuperAdmin && !["tenants", "countries", "cities"].includes(active) && !tenant) {
      setRows([]);
      setTotal(0);
      return;
    }
    let alive = true;
    setLoading(true);
    setError("");
    (active === "permissions"
      ? allRows(active).then((catalog) => {
          const matches = catalog.filter((row) => permissionMatches(row, query, permissionMessages));
          return {items: matches, total: matches.length, page: 1, pageSize: matches.length};
        })
      : api<Result>(
      scope(
        `/data/${active}?page=${page}&pageSize=25&search=${encodeURIComponent(query)}`,
      ),
    ))
      .then((data) => {
        if (alive) {
          setRows(data.items);
          setTotal(data.total);
          if (data.items.length === 0 && page > 1) setPage((p) => p - 1);
        }
      })
      .catch((e) => {
        if (alive) {
          setRows([]);
          setTotal(0);
          setError(translateError(e));
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [session, active, tenant, page, query, version, scope, allRows, translateError]);
  useEffect(() => {
    if (!navigationReady || !session || !active || !canOpenResource(session, active)) return;
    try {
      sessionStorage.setItem(`workspace:${session.id}:${tenant}:${active}`, JSON.stringify({search, page}));
      const url = `${window.location.pathname}?view=${encodeURIComponent(active)}`;
      if (window.location.pathname + window.location.search !== url) window.history.replaceState(null, "", url);
    } catch { /* Navigation remains usable when storage or history is blocked. */ }
  }, [navigationReady, session, tenant, active, search, page]);
  useEffect(() => {
    if (!navigationReady || !session) return;
    const onPopState = () => {
      if (editor) clearRecordRecovery(session, tenant, editor.resource.key);
      const allowed = [...resources.map(item => item.key), ...Object.keys(partnerSettingsParents)].filter(key => canOpenResource(session, key));
      const route = workspaceRoute(window.location.search, allowed) || resources.find(item => !settingsCatalogs.includes(item.key) && canOpenResource(session, item.key))?.key || "";
      setActive(route); setSearch(""); setQuery(""); setPage(1); setNotice(""); setEditor(null); setDeleting(null);
      try {
        const stored = JSON.parse(sessionStorage.getItem(`workspace:${session.id}:${tenant}:${route}`) || "null");
        if (stored && typeof stored.search === "string" && Number.isSafeInteger(stored.page) && stored.page > 0) {
          setSearch(stored.search); setQuery(stored.search); setPage(stored.page);
        }
      } catch { /* Ignore unavailable or invalid storage. */ }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [navigationReady, session, resources, tenant, editor]);
  const resource = resources.find((x) => x.key === active);
  const recoveryOpened = useRef("");
  useEffect(() => {
    if (!navigationReady || !session || !resource || !active) return;
    const key = recordRecoveryKey(session, tenant, active);
    if (recoveryOpened.current === key) return;
    recoveryOpened.current = key;
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || "null");
      if (saved?.kind === "create" && !resource.readOnly && can(session, active, "create")) setEditor({resource, row: null});
    } catch { /* Ignore invalid or unavailable storage. */ }
  }, [navigationReady, session, tenant, active, resource]);
  const accessible = useMemo(
    () => resources.filter((x) => session && canOpenResource(session, x.key)),
    [resources, session],
  );
  const refreshSession = useCallback(async () => {
    try {
      const fresh = await api<Session>("/session");
      setSession(fresh);
      if (!canOpenResource(fresh, active)) {
        setRows([]);
        setTotal(0);
        setActive(resources.find((entry) => !settingsCatalogs.includes(entry.key) && canOpenResource(fresh, entry.key))?.key || "");
        setPage(1);
      }
      setEditor((current) => current && can(fresh, current.resource.key, current.row ? "read" : "create", current.row) ? current : null);
      setDeleting(null);
      setResetUser(null);
      setVersion((v) => v + 1);
      return fresh;
    } catch (e) {
      setSession(null);
      setRows([]);
      setEditor(null);
      throw e;
    }
  }, [active, resources]);
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const s = await api<Session>("/auth/login", "POST", {
        username,
        password,
        ...(tenantCode ? { tenantCode } : {}),
      });
      await refreshCsrf();
      rememberWorkspaceTenant(s, s.selectedTenantId ?? s.tenantId ?? "");
      setPassword("");
      document.cookie = `locale=${s.preferredLanguage}; Path=/; Max-Age=31536000; SameSite=Strict`;
      if (s.preferredLanguage !== locale) {
        location.reload();
        return;
      }
      setSession(s);
      setTenant(s.selectedTenantId ?? s.tenantId ?? "");
      setVersion((v) => v + 1);
    } catch (e) {
      setError(translateError(e));
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    setBusy(true);
    try {
      await api("/auth/logout", "POST");
      if (session) clearBusinessPartnerRecoveries(session);
      if (session) clearUserProfileRecoveries(session);
      setProfileOpen(false);
      try {
        if (session) sessionStorage.removeItem(workspaceTenantKey(session));
        const prefix = `workspace:${session?.id}:`;
        for (let i = sessionStorage.length - 1; i >= 0; i--) {
          const key = sessionStorage.key(i);
          if (key?.startsWith(prefix)) {
            const match = key.match(/^workspace:([^:]+):([^:]+):record:(.+)$/);
            if (!match || !sessionStorage.getItem(`record-pending:${match[1]}:${match[2]}:${match[3]}`)) sessionStorage.removeItem(key);
          }
        }
        window.history.replaceState(null, "", window.location.pathname);
      } catch { /* Storage may be disabled. */ }
      restoredNavigation.current = false;
      setNavigationReady(false);
      setSearch(""); setQuery(""); setPage(1);
      setSession(null);
      setRows([]);
      setResources([]);
      setTenants([]);
      setTenant("");
      setActive("");
      setNotice("");
      setError("");
      await refreshCsrf();
    } catch (e) {
      setError(translateError(e));
    } finally {
      setBusy(false);
    }
  }
  function navigate(key: string) {
    if (session && editor) clearRecordRecovery(session, tenant, editor.resource.key);
    if (session) clearProfileRecovery(session, tenant);
    if (key !== active && typeof window !== "undefined") {
      try { window.history.pushState(null, "", `${window.location.pathname}?view=${encodeURIComponent(key)}`); } catch { /* History may be disabled. */ }
    }
    if (key === "business-partners") {
      if (session) resetBusinessPartnerRecovery(session, tenant);
      setPartnerWorkspaceVersion(current => current + 1);
    }
    if (key === "business-partner-numbering" && session) resetBusinessPartnerNumberingRecovery(session, tenant);
    setWorkspaceVersion(current => current + 1);
    setActive(key);
    setEditor(null);
    setDeleting(null);
    setProfileOpen(false);
    setResetUser(null);
    setSearch("");
    setQuery("");
    setPage(1);
    setNotice("");
    setError("");
  }
  async function saved(row: Row, key: string) {
    setEditor(null);
    await refreshSession();
    setNotice(t("saved"));
    if (key === "tenants") {
      await loadTenants();
      if (!tenant) setTenant(row.id);
    }
    setEditor(null);
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api(scope(`/data/${active}/${deleting.id}`), "DELETE");
      if (active === "tenants") {
        const list = await loadTenants();
        if (tenant === deleting.id) setTenant(list[0]?.id || "");
      }
      setDeleting(null);
      await refreshSession();
      setNotice(t("saved"));
    } catch (e) {
      setError(translateError(e));
    } finally {
      setBusy(false);
    }
  }
  if (initial)
    return (
      <div className="startup">
        <Brand />
        <span role="status">{t("loading")}</span>
      </div>
    );
  if (!session)
    return (
      <main className="flex min-h-svh flex-col items-center justify-center gap-6 bg-background p-6 md:p-10">
        <div className="absolute right-6 top-6"><LocaleControl /></div>
        <Brand />
        <Card className="w-full max-w-sm">
          <CardHeader><CardTitle className="text-2xl"><h1>{t("login")}</h1></CardTitle></CardHeader>
          <CardContent><form onSubmit={login}>
            <Notice message={error} />
            <div className="field">
              <Label htmlFor="username">{t("username")}</Label>
              <Input
                id="username"
                value={username}
                autoComplete="username"
                required
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="field">
              <Label htmlFor="password">{t("password")}</Label>
              <Input
                id="password"
                type="password"
                value={password}
                autoComplete="current-password"
                required
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div className="field">
              <Label htmlFor="tenant-code">{t("tenantCode")}</Label>
              <Input
                id="tenant-code"
                autoComplete="organization"
                value={tenantCode}
                onChange={(e) => setTenantCode(e.target.value)}
              />
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? t("loading") : t("login")}
              <ArrowRight size={17} />
            </Button>
          </form></CardContent>
        </Card>
      </main>
    );
  if (session.mustChangePassword)
    return (
      <main className="password-page">
        <Card className="w-full max-w-sm p-6">
          <Brand />
          <h1>{t("changePassword")}</h1>
          <PasswordForm
            onSaved={async () => {
              setSession(await api<Session>("/session"));
              await refreshCsrf();
              setProfileOpen(false);
            }}
            onError={translateError}
          />
          <Button variant="ghost" onClick={logout} disabled={busy}>
            {t("logout")}
          </Button>
        </Card>
      </main>
    );
  const needTenant = session.isSuperAdmin && !["tenants", "countries", "cities", "settings", "settings-master-data", "settings-business-partners"].includes(active) && !tenant;
  const pageTitle = (key: string) => key === "settings-master-data" ? t("masterData")
    : key === "settings-business-partners" ? r("business-partners")
    : key === "business-partner-numbering" ? t("numbering") : r(key);
  const settingsTrail: string[] = [];
  for (let key = partnerSettingsParents[active]; key; key = partnerSettingsParents[key]) settingsTrail.unshift(key);
  const heading = <div>
    <div className="eyebrow">
      {settingsTrail.length ? settingsTrail.map((key, index) => <span key={key}>{index > 0 && <span aria-hidden="true"> › </span>}<button type="button" onClick={() => navigate(key)}>{pageTitle(key)}</button></span>) : t(sections.find((s) => s.keys.includes(active))?.label || "administration")}
    </div>
    <h1>{active ? pageTitle(active) : t("noAccess")}</h1>
  </div>;
  const showPartnerWorkspace = active === "business-partners" && !needTenant && canOpenResource(session, active);
  const nextSettingsPage = Object.keys(partnerSettingsParents).find(key => partnerSettingsParents[key] === active);
  const settingsTile = nextSettingsPage && can(session, "business-partner-numbering", "read") && <button type="button" className="rounded-xl border bg-card p-6 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => navigate(nextSettingsPage)}>
    {nextSettingsPage === "business-partner-numbering" ? <Settings className="mb-4 size-8 text-primary" /> : <UsersRound className="mb-4 size-8 text-primary" />}<h2 className="text-lg font-semibold">{pageTitle(nextSettingsPage)}</h2>
  </button>;
  const columns = tableFields(resource);
  return (
    <SidebarProvider>
      <a className="skip-link" href="#main">
        {t("workspace")}
      </a>
      <WorkspaceNavigation accessible={accessible} active={active} navigate={navigate} session={session} />
      <SidebarInset className="min-w-0">
        <header className="topbar">
          <div className="topbar-leading">
            <SidebarTrigger aria-label={t("menu")} />
            <Separator orientation="vertical" className="h-4" />
            <span className="breadcrumb">
              {t("workspace")}
              <ChevronRight size={14} />
              <strong>{active ? pageTitle(active) : t("administration")}</strong>
            </span>
          </div>
          <div className="topbar-actions">
            <LocaleControl />
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <Button variant="ghost" aria-label={t("personalProfile")} className="max-w-48 gap-2 px-2">
                  <UserRound size={18} className="shrink-0" />
                  <span className="hidden truncate sm:inline">{session.displayName || session.username}</span>
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal><DropdownMenu.Content align="end" sideOffset={6} className="z-50 min-w-52 rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                <DropdownMenu.Label className="px-2 py-2 text-sm">
                  <span className="block font-medium">{session.displayName}</span><span className="block text-xs text-muted-foreground">{session.username}</span>
                </DropdownMenu.Label>
                <DropdownMenu.Separator className="my-1 h-px bg-border" />
                <DropdownMenu.Item id="personal-profile-menu-item" onSelect={() => {
                  const key = profileRecoveryKey(session, tenant);
                  try { if (key) sessionStorage.setItem(key, "1"); } catch { /* Storage is optional. */ }
                  setProfileOpen(true);
                }} className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent">
                  <UserRound size={16} />{t("personalProfile")}
                </DropdownMenu.Item>
                <DropdownMenu.Item id="user-logout-menu-item" disabled={busy} onSelect={() => { void logout(); }} className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm outline-none focus:bg-accent data-[disabled]:opacity-50">
                  <LogOut size={16} />{t("logout")}
                </DropdownMenu.Item>
              </DropdownMenu.Content></DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>
        </header>
        {session.isSuperAdmin && (
          <div className="tenant-bar">
            <Building2 size={17} />
            <Label htmlFor="tenant-select">{t("tenant")}</Label>
            <Select value={tenant || "__none__"} onValueChange={(value) => {
              if (editor) clearRecordRecovery(session, tenant, editor.resource.key);
              clearProfileRecovery(session, tenant);
              setProfileOpen(false);
              setEditor(null);
              setTenant(value === "__none__" ? "" : value);
              setPage(1); setSearch(""); setQuery(""); setNotice("");
            }}>
              <SelectTrigger id="tenant-select" className="w-full sm:w-72"><SelectValue placeholder={t("selectTenant")} /></SelectTrigger>
              <SelectContent><SelectItem value="__none__">{t("selectTenant")}</SelectItem>
                {tenants.map(row => <SelectItem key={row.id} value={row.id}>{rowLabel(row)}{row.is_enabled === false ? ` · ${t("disabled")}` : ""}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const meta = resources.find((x) => x.key === "tenants");
                if (meta) setEditor({ resource: meta, row: null });
              }}
              disabled={!resources.some((x) => x.key === "tenants")}
            >
              <Plus size={15} />
              <span>{t("createTenant")}</span>
            </Button>
          </div>
        )}
        <section id="main" className="workspace" tabIndex={-1}>
          {settingsCatalogs.includes(active) && <Button variant="outline" className="mb-4" onClick={() => navigate("settings")}>{t("backToSettings")}</Button>}
          {active in partnerSettingsParents && <Button variant="outline" className="mb-4" onClick={() => navigate(partnerSettingsParents[active])}>{t(active === "business-partner-numbering" ? "backToBusinessPartners" : active === "settings-business-partners" ? "backToMasterData" : "backToSettings")}</Button>}
          {!showPartnerWorkspace && <div className="page-heading">
            {heading}
            {resource && !["settings", "business-partners", "business-partner-numbering"].includes(active) && !resource.readOnly && !needTenant && can(session, active, "create") && (
              <Button onClick={() => setEditor({ resource, row: null })}>
                <Plus size={17} />
                {t("new")}
              </Button>
            )}
          </div>}
          <Notice message={error} />
          {notice && (
            <div className="success" role="status">
              <Check size={16} />
              {notice}
            </div>
          )}
          {active === "settings" && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label={r("settings")}>
            {settingsCatalogs.filter(key => accessible.some(item => item.key === key)).map(key => {
              const Icon = icons[key];
              return <button key={key} type="button" className="rounded-xl border bg-card p-6 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => navigate(key)}>
                <Icon className="mb-4 size-8 text-primary" /><h2 className="text-lg font-semibold">{r(key)}</h2>
              </button>;
            })}
            {settingsTile}
          </div>}
          {active === "settings-master-data" || active === "settings-business-partners" ? canOpenResource(session, active) && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{settingsTile}</div> : active === "settings" && !needTenant ? null : needTenant ? (
            <Card className="empty-state">
              <span className="empty-icon">
                <Building2 size={32} />
              </span>
              <h2>{tenants.length ? t("selectTenant") : t("noTenants")}</h2>
              {!tenants.length && (
                <Button
                  onClick={() => {
                    const meta = resources.find((x) => x.key === "tenants");
                    if (meta) setEditor({ resource: meta, row: null });
                  }}
                >
                  <Plus size={17} />
                  {t("createTenant")}
                </Button>
              )}
            </Card>
          ) : active === "business-partners" && canOpenResource(session, active) ? (
            <BusinessPartnerWorkspace key={`${tenant}:${partnerWorkspaceVersion}`} session={session} tenantId={tenant} scope={scope} onError={translateError} heading={heading} />
          ) : active === "business-partner-numbering" && can(session, active, "read") ? (
            <BusinessPartnerNumbering key={`${tenant}:${workspaceVersion}`} session={session} tenantId={tenant} scope={scope} onError={translateError} />
          ) : resource ? (
            <Card id={active === "settings" ? "settings-panel-general" : undefined} role={active === "settings" ? "tabpanel" : undefined} aria-labelledby={active === "settings" ? "settings-tab-general" : undefined} className="gap-0 overflow-hidden py-0" aria-label={r(active)}>
              <div className="table-toolbar">
                <div className="search-box">
                  <Search size={17} />
                  <Input
                    aria-label={t("search")}
                    value={search}
                    placeholder={t("search")}
                    onChange={(e) => {setSearch(e.target.value); setPage(1);}}
                  />
                </div>
                <div className="table-count">
                  {total} {t("records", { count: total })}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("refresh")}
                  onClick={async () => {
                    try { await refreshSession(); }
                    catch (e) { setError(translateError(e)); }
                  }}
                  disabled={loading}
                >
                  <RefreshCw
                    size={16}
                    className={loading ? "animate-spin" : ""}
                  />
                </Button>
              </div>
              {active === "permissions" ? <div className="p-4" aria-busy={loading}>
                {loading ? <p role="status" className="p-4 text-sm text-muted-foreground">{t("loading")}</p> :
                  <PermissionTree rows={rows} query={query} renderLeaf={row => <div className="flex min-w-0 items-center gap-3 px-2 py-3 text-sm">
                    <div className="min-w-0 flex-1">
                      <span className="font-medium">{localizedRowLabel(active, row, locale)}</span>
                      <code className="block break-all text-xs text-muted-foreground">{String(row.code ?? "")}</code>
                    </div>
                    {row.is_enabled === false && <Badge variant="secondary">{t("disabled")}</Badge>}
                    <Button type="button" variant="ghost" size="sm" aria-label={`${t("details")} ${localizedRowLabel(active, row, locale)}`} onClick={() => setEditor({resource, row})}>
                      {t("details")}
                    </Button>
                  </div>} />}
              </div> : <>
              <div className="table-scroll" aria-busy={loading}>
                <Table>
                  <TableHeader>
                    <TableRow>
                      {columns.map((col) => (
                        <TableHead key={col.name} scope="col">
                          {f(col.name)}
                        </TableHead>
                      ))}
                      <TableHead scope="col" className="actions-cell">
                        {t("actions")}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {!rows.length ? (
                      <TableRow>
                        <TableCell colSpan={columns.length + 1}>
                          <div className="table-empty">
                            <Boxes size={32} />
                            <span>{loading ? t("loading") : t("empty")}</span>
                            {!loading && !resource.readOnly && can(session, active, "create") && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  setEditor({ resource, row: null })
                                }
                              >
                                <Plus size={15} />
                                {t("new")}
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ) : (
                      rows.map((row) => (
                        <TableRow key={row.id}>
                          {columns.map((col, i) => (
                            <TableCell
                              key={col.name}
                              className={active === "sites" && col.name === "address" ? "min-w-64 whitespace-normal" : i === 0 ? "primary-cell" : ""}
                            >
                              {active === "sites" && col.name === "address" ? siteAddress(row, locale) : col.type === "boolean" ? (
                                <Badge
                                  variant={
                                    row[col.name] ? "default" : "secondary"
                                  }
                                >
                                  {row[col.name] ? t("enabled") : t("disabled")}
                                </Badge>
                              ) : col.type === "reference" ? (
                                <ReferenceName
                                  rowId={String(row[col.name] || "")}
                                  resource={col.reference!}
                                  load={allRows}
                                />
                              ) : (
                                active === "permissions" && col.name === "name"
                                  ? localizedRowLabel(active, row, locale)
                                  : formatFieldValue(col, row[col.name], locale, languages, option => classificationOptionLabel(col.name, option, locale))
                              )}
                            </TableCell>
                          ))}
                          <TableCell className="actions-cell">
                            <div className="row-actions">
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`${!resource.readOnly && can(session, active, "update", row) ? t("edit") : t("details")} ${localizedRowLabel(active, row, locale)}`}
                                onClick={() => setEditor({ resource, row })}
                              >
                                <Pencil size={15} />
                              </Button>
                              {active === "users" &&
                                can(session, "users", "reset_password", row) && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    aria-label={`${t("resetPassword")} ${rowLabel(row)}`}
                                    onClick={() => setResetUser(row)}
                                  >
                                    <KeyRound size={15} />
                                  </Button>
                                )}
                              {!resource.readOnly && can(session, active, "delete", row) && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="delete-action"
                                  aria-label={`${t("delete")} ${rowLabel(row)}`}
                                  onClick={() => {
                                    setError("");
                                    setDeleting(row);
                                  }}
                                >
                                  <Trash2 size={15} />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
              <div className="pagination">
                <span>
                  {t("page")} {page} {t("of")}{" "}
                  {Math.max(1, Math.ceil(total / 25))}
                </span>
                <div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p - 1)}
                    disabled={page <= 1 || loading}
                  >
                    <ChevronLeft size={15} />
                    {t("previous")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page * 25 >= total || loading}
                  >
                    {t("next")}
                    <ChevronRight size={15} />
                  </Button>
                </div>
              </div>
              </>}
            </Card>
          ) : null}
        </section>
        <footer className="app-footer">
          <span>Enginia360</span>
          <span>
            {tenant
              ? rowLabel(tenants.find((x) => x.id === tenant) || { id: tenant })
              : session.displayName}
          </span>
        </footer>
      </SidebarInset>
      {editor && (
        <RecordEditor
          key={`${editor.resource.key}-${editor.row?.id || "new"}`}
          resource={editor.resource}
          row={editor.row}
          canWrite={!editor.resource.readOnly && can(session, editor.resource.key, editor.row ? "update" : "create", editor.row)}
          session={session}
          tenant={tenant}
          scope={scope}
          load={allRows}
          onClose={() => {clearRecordRecovery(session, tenant, editor.resource.key); setEditor(null);}}
          onSaved={saved}
          onError={translateError}
        />
      )}
      <AlertDialog
        open={!!deleting}
        onOpenChange={(open) => {
          if (!open && !busy) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {deleting ? rowLabel(deleting) : ""} · {t("deleteText")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Notice message={error} />
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>
              {t("cancel")}
            </AlertDialogCancel>
            <Button variant="destructive" onClick={remove} disabled={busy}>
              {t("delete")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {profileOpen && <ProfileDialog
        session={{...session, selectedTenantId: tenant, tenantId: tenant}}
        onClose={() => { clearProfileRecovery(session, tenant); setProfileOpen(false); }}
        onError={translateError}
        onSaved={fresh => {
          setSession(fresh);
          setNotice(t("profileSaved"));
        }}
      />}
      <Dialog
        open={!!resetUser}
        onOpenChange={(open) => {
          if (!open) {
            setProfileOpen(false);
            setResetUser(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {t("resetPassword")}
            </DialogTitle>
            <DialogDescription>
              {resetUser ? rowLabel(resetUser) : ""}
            </DialogDescription>
          </DialogHeader>
          <PasswordForm
            resetId={resetUser?.id}
            scope={scope}
            onError={translateError}
            onSaved={async () => {
              setResetUser(null);
              setProfileOpen(false);
              setNotice(t("passwordSaved"));
            }}
          />
        </DialogContent>
      </Dialog>
    </SidebarProvider>
  );
}

let referenceCache = new WeakMap<
  (key: string) => Promise<Row[]>,
  Map<string, Promise<Row[]>>
>();
function ReferenceName({
  rowId,
  resource,
  load,
}: {
  rowId: string;
  resource: string;
  load: (key: string) => Promise<Row[]>;
}) {
  const [label, setLabel] = useState("");
  useEffect(() => {
    let alive = true;
    if (!rowId) {
      setLabel("—");
      return;
    }
    let cache = referenceCache.get(load);
    if (!cache) {
      cache = new Map();
      referenceCache.set(load, cache);
    }
    let promise = cache.get(resource);
    if (!promise) {
      promise = load(resource);
      cache.set(resource, promise);
      promise.catch(() => cache!.delete(resource));
    }
    promise
      .then((rows) => {
        if (alive)
          setLabel(
            rows.find((x) => x.id === rowId)
              ? rowLabel(rows.find((x) => x.id === rowId)!)
              : "—",
          );
      })
      .catch(() => {
        if (alive) setLabel("—");
      });
    return () => {
      alive = false;
    };
  }, [rowId, resource, load]);
  return <span>{label || "…"}</span>;
}

function RecordEditor({
  resource,
  row,
  canWrite,
  session,
  tenant,
  scope,
  load,
  onClose,
  onSaved,
  onError,
}: {
  resource: Resource;
  row: Row | null;
  canWrite: boolean;
  session: Session;
  tenant: string;
  scope: (path: string) => string;
  load: (key: string) => Promise<Row[]>;
  onClose: () => void;
  onSaved: (row: Row, key: string) => Promise<void>;
  onError: (e: unknown) => string;
}) {
  const locale = useLocale();
  const t = useTranslations("app"),
    f = useTranslations("fields"),
    languages = useTranslations("languages"),
    fieldOptions = useTranslations("fieldOptions"),
    r = useTranslations("resources");
  const [values, setValues] = useState<Record<string, unknown>>(() =>
      Object.fromEntries(
        resource.fields.map((field) => [
          field.name,
          row
            ? resource.key === "permissions" && field.name === "name"
              ? localizedRowLabel(resource.key, row, locale)
              : field.type === "json"
              ? JSON.stringify(row[field.name], null, 2)
              : (row[field.name] ?? (field.type === "multiselect" ? [] : field.defaultValue ?? ""))
            : field.type === "boolean"
              ? true
              : field.type === "json"
                ? "{}"
                : field.type === "multiselect" ? [] : field.defaultValue ?? "",
        ]),
      ),
    ),
    [refs, setRefs] = useState<Record<string, Row[]>>({}),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [refsLoading, setRefsLoading] = useState(resource.fields.some(field => field.reference)),
    [drafts, setDrafts] = useState<Record<string, RelationDraft>>({}),
    [relationsLoading, setRelationsLoading] = useState(true),
    [relationsError, setRelationsError] = useState(""),
    [refsFailed, setRefsFailed] = useState(false),
    [coverageDraft, setCoverageDraft] = useState<CoverageDraft>(),
    [coverageLoading, setCoverageLoading] = useState(true),
    [coverageError, setCoverageError] = useState("");
  const coverageVisible = resource.key === "purchasing-organizations" && can(session, resource.key, "read") && can(session, "companies", "read") && can(session, "sites", "read");
  const coverageEditable = coverageVisible && can(session, resource.key, "assign_scope");
  const owner = row ?? {id: "", tenant_id: session.tenantId ?? "new"};
  const visibleRelations = (relations[resource.key] ?? []).filter(relation => canRelation(session, resource.key, relation.key, "read", owner));
  const editableRelations = visibleRelations.filter(relation => canRelation(session, resource.key, relation.key, "assign", owner));
  const canSave = canWrite || editableRelations.length > 0 || coverageEditable;
  const submitting = useRef(false);
  const recoveryKey = recordRecoveryKey(session, tenant, resource.key);
  const pendingKey = recordPendingKey(session, tenant, resource.key);
  const [uncertainCreate, setUncertainCreate] = useState(false);
  const recovery = useRef<any>(null);
  const [recoveryReady, setRecoveryReady] = useState(false);
  useEffect(() => {
    if (!row && canWrite) {
      try {
        setUncertainCreate(!!sessionStorage.getItem(pendingKey));
        const saved = JSON.parse(sessionStorage.getItem(recoveryKey) || "null");
        if (saved?.kind === "create") {
          recovery.current = saved;
          if (saved.values && typeof saved.values === "object") setValues(old => ({...old, ...recoverableValues(resource.fields, saved.values)}));
        }
      } catch { /* Ignore invalid or unavailable storage. */ }
    }
    setRecoveryReady(true);
  }, [recoveryKey, row, canWrite, resource.fields]);
  useEffect(() => {
    let alive = true;
    setRelationsLoading(true);
    setRelationsError("");
    Promise.all((relations[resource.key] ?? []).filter(relation => canRelation(session, resource.key, relation.key, "read", row ?? {id: "", tenant_id: session.tenantId ?? "new"})).map(async relation => {
      const [options, data] = await Promise.all([
        load(relation.target),
        row ? api<{ids: string[]}>(scope(`/links/${relation.key}/${row.id}`)) : Promise.resolve({ids: [] as string[]}),
      ]);
      return [relation.key, {options: relationOptions(relation.target, options), initialIds: data.ids, ids: data.ids}] as const;
    })).then(entries => {
      if (alive) setDrafts(Object.fromEntries(entries.map(([key, draft]) => {
        const saved = recovery.current?.links?.[key];
        return [key, {...draft, ids: Array.isArray(saved) && saved.every((id: unknown) => typeof id === "string") ? saved : draft.ids}];
      })));
    }).catch(e => {
      if (alive) setRelationsError(onError(e));
    }).finally(() => {
      if (alive) setRelationsLoading(false);
    });
    return () => {alive = false};
  }, [resource, row, session, load, scope, onError]);
  useEffect(() => {
    let alive = true;
    const keys = [
      ...new Set(
        resource.fields.filter((x) => x.reference).map((x) => x.reference!),
      ),
    ];
    setRefsLoading(true);
    setRefsFailed(false);
    Promise.all(keys.map(async (key) => [key, await load(key)] as const))
      .then((entries) => {
        if (alive) setRefs(Object.fromEntries(entries));
      })
      .catch((e) => {
        if (alive) {setRefsFailed(true); setError(onError(e));}
      })
      .finally(() => {
        if (alive) setRefsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [resource, load, onError]);
  useEffect(() => {
    if (!coverageVisible) return;
    let alive = true;
    setCoverageLoading(true);
    setCoverageError("");
    Promise.all([
      load("companies"), load("sites"),
      row ? api<{coverage: CoverageEntry[]}>(scope(`/data/purchasing-organizations/${row.id}/coverage`)) : Promise.resolve({coverage: [] as CoverageEntry[]}),
    ]).then(([companies, sites, data]) => {
      if (alive) setCoverageDraft({companies, sites, initial: data.coverage, coverage: Array.isArray(recovery.current?.coverage) ? recovery.current.coverage : data.coverage});
    }).catch(e => {if (alive) setCoverageError(onError(e));})
      .finally(() => {if (alive) setCoverageLoading(false);});
    return () => {alive = false};
  }, [coverageVisible, row, load, scope, onError]);
  useEffect(() => {
    if (row || !canWrite || !recoveryReady || relationsLoading || relationsError || (coverageVisible && (coverageLoading || coverageError || !coverageDraft))) return;
    try {
      const links = Object.fromEntries(editableRelations.filter(relation => drafts[relation.key]).map(relation => [relation.key, drafts[relation.key].ids]));
      sessionStorage.setItem(recoveryKey, JSON.stringify({kind: "create", values: recoverableValues(resource.fields, values), links, ...(coverageEditable && coverageDraft ? {coverage: coverageDraft.coverage} : {})}));
    } catch { /* Storage is optional. */ }
  }, [row, canWrite, recoveryReady, relationsLoading, relationsError, coverageVisible, coverageLoading, coverageError, coverageDraft, coverageEditable, drafts, values, recoveryKey, resource.fields]);
  const set = (name: string, value: unknown) =>
    setValues((old) => ({ ...old, [name]: value }));
  const missingRequired = resource.fields.some(field => {
    if (!field.required || field.type === "boolean") return false;
    const value = values[field.name];
    return value == null || (typeof value === "string" && !value.trim()) || (Array.isArray(value) && value.length === 0);
  });
  const changedLinks = Object.fromEntries(editableRelations.filter(relation => {
    const draft = drafts[relation.key];
    return draft && (draft.ids.length !== draft.initialIds.length || draft.ids.some(id => !draft.initialIds.includes(id)));
  }).map(relation => [relation.key, drafts[relation.key].ids]));
  let changedValues: Record<string, unknown> = {};
  let invalidValues = false;
  if (canWrite) {
    try {
      const normalized = normalizeValues(resource.fields, values);
      // L'ordine iniziale dei multiselect non rende modificato lo stesso insieme.
      const initial = row ? {...row, ...normalizeValues(resource.fields.filter(field => field.type === "multiselect"), row)} : null;
      changedValues = initial ? Object.fromEntries(Object.entries(normalized).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(initial[key] ?? null))) : normalized;
    } catch {invalidValues = true;}
  }
  const pendingRelations = editableRelations.length > 0 && (relationsLoading || !!relationsError || editableRelations.some(relation => !drafts[relation.key]));
  const changedCoverage = coverageEditable && !!coverageDraft && coverageChanged(coverageDraft);
  const pendingCoverage = coverageVisible && (coverageLoading || !!coverageError || !coverageDraft || (coverageEditable && !coverageValid(coverageDraft)));
  const hasChanges = !row && canWrite || invalidValues || Object.keys(changedValues).length > 0 || Object.keys(changedLinks).length > 0 || changedCoverage;
  const fiscalFields = resource.key === "sites" && resource.fields.some(field => field.name === "vat_number") && resource.fields.some(field => field.name === "tax_code");
  const missingFiscal = fiscalFields && !String(values.vat_number ?? "").trim() && !String(values.tax_code ?? "").trim();
  const blocked = (!row && (!recoveryReady || uncertainCreate)) || missingFiscal || busy || (canWrite && (refsLoading || missingRequired || refsFailed)) || pendingRelations || pendingCoverage || !hasChanges;
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSave || blocked || submitting.current) return;
    setError("");
    if (invalidValues) {setError(t("jsonInvalid")); return;}
    const body = {
      ...((!row && canWrite || Object.keys(changedValues).length > 0) ? {values: changedValues} : {}),
      ...(Object.keys(changedLinks).length > 0 ? {links: changedLinks} : {}),
      ...(changedCoverage ? {coverage: coverageDraft!.coverage} : {}),
    };
    if (!row) {
      try {
        if (sessionStorage.getItem(pendingKey)) {setUncertainCreate(true); return;}
        const links = Object.fromEntries(editableRelations.filter(relation => drafts[relation.key]).map(relation => [relation.key, drafts[relation.key].ids]));
        sessionStorage.setItem(recoveryKey, JSON.stringify({kind: "create", values: recoverableValues(resource.fields, values), links, ...(coverageEditable && coverageDraft ? {coverage: coverageDraft.coverage} : {})}));
        sessionStorage.setItem(pendingKey, "pending");
        if (sessionStorage.getItem(pendingKey) !== "pending") throw new Error("storage unavailable");
      } catch {setError(t("createStorageUnavailable")); return;}
    }
    submitting.current = true;
    setBusy(true);
    let result: Row;
    try {
      result = await api<Row>(scope(`/data/${resource.key}${row ? `/${row.id}` : ""}/save`), row ? "PUT" : "POST", body);
    } catch (e) {
      if (!row) {
        const rejected = e instanceof ApiError && [400, 401, 403, 404, 409, 422].includes(e.status);
        if (rejected) {
          try {sessionStorage.removeItem(pendingKey);} catch {setUncertainCreate(true);}
          setError(onError(e));
        } else {setUncertainCreate(true); setError(t("createOutcomeUncertain"));}
      } else setError(onError(e));
      submitting.current = false;
      setBusy(false);
      return;
    }
    if (!row) {try {sessionStorage.removeItem(pendingKey);} catch { /* Keep the conservative lock. */ }}
    // Il commit è concluso: un refresh fallito non deve rendere ripetibile il salvataggio.
    referenceCache = new WeakMap();
    onClose();
    try {await onSaved(result, resource.key);} catch (e) {onError(e);}
    finally {setBusy(false);}
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {r(resource.key)} ·{" "}
            {canWrite ? (row ? t("edit") : t("new")) : t("details")}
          </DialogTitle>
          <DialogDescription>
            {row ? localizedRowLabel(resource.key, row, locale) : r(resource.key)}
          </DialogDescription>
        </DialogHeader>
        <div className="editor-scroll">
          <form onSubmit={submit} id="record-form">
            <Notice message={uncertainCreate ? t("createOutcomeUncertain") : error} />

            <fieldset disabled={!canWrite || busy} className="form-grid">
              {resource.fields.map((field) => {
                const id = `field-${field.name}`;
                let options = field.reference
                  ? refs[field.reference] || []
                  : [];
                if (
                  resource.key === "settings" &&
                  field.name === "site_id" &&
                  values.company_id
                )
                  options = options.filter(
                    (x) => x.company_id === values.company_id,
                  );
                if (field.type === "multiselect") {
                  const selected = Array.isArray(values[field.name]) ? values[field.name] as string[] : [];
                  return <fieldset key={field.name} id={id} className="field field-wide" disabled={!canWrite || busy}>
                    <legend className="text-sm font-medium">{f(field.name)}</legend>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {(field.options ?? []).map(option => <div key={option} className="flex items-center gap-2">
                        <Checkbox id={`${id}-${option}`} checked={selected.includes(option)} disabled={!canWrite || busy}
                          onCheckedChange={checked => {
                            if (!canWrite || busy) return;
                            setValues(old => {
                              const current = Array.isArray(old[field.name]) ? old[field.name] as string[] : [];
                              return {...old, [field.name]: (field.options ?? []).filter(value => value === option ? checked === true : current.includes(value))};
                            });
                          }} />
                        <Label htmlFor={`${id}-${option}`}>{fieldOptions(`${field.name}.${option}`)}</Label>
                      </div>)}
                    </div>
                  </fieldset>;
                }
                return (
                  <div
                    className={`field ${["textarea", "json"].includes(field.type) ? "field-wide" : ""} ${field.type === "boolean" ? "switch-field" : ""}`}
                    key={field.name}
                  >
                    <Label htmlFor={id}>
                      {f(field.name)}
                      {field.required && <span aria-hidden="true"> *</span>}
                    </Label>
                    {resource.key === "sites" && field.name === "country_code" ? (
                      <SiteCountrySelect id={id} value={String(values[field.name] ?? "")} scope={scope} disabled={!canWrite || busy} readOnly={!canWrite} required={field.required}
                        onChange={value => {if (canWrite && !busy) set(field.name, value);}} />
                    ) : resource.key === "sites" && ["address", "city", "province", "postal_code"].includes(field.name) ? (
                      <AddressAutocomplete id={id} field={field.name as AddressField} value={String(values[field.name] ?? "")} context={values} scope={scope}
                        disabled={!canWrite || busy} required={field.required}
                        onChange={text => {if (canWrite && !busy) set(field.name, text);}}
                        onSelect={item => {if (canWrite && !busy) setValues(old => {
                          const selected = addressSelection(old, field.name as AddressField, item);
                          return Object.fromEntries(Object.entries(selected).filter(([key]) => resource.fields.some(f => f.name === key)));
                        });}} />
                    ) : field.type === "boolean" ? (
                      <Switch
                        id={id}
                        checked={Boolean(values[field.name])}
                        onCheckedChange={(value) => set(field.name, value)}
                      />
                    ) : field.type === "select" ? (
                      <Select
                        name={field.name}
                        required={field.required}
                        value={String(values[field.name] ?? field.defaultValue ?? "")}
                        disabled={!canWrite || busy}
                        onValueChange={(value) => {
                          if (!canWrite || busy) return;
                          set(field.name, value === "__none__" ? "" : value);
                        }}
                      >
                        <SelectTrigger id={id} className="w-full" aria-label={f(field.name)}><SelectValue placeholder="—" /></SelectTrigger>
                        <SelectContent>
                          {!field.required && !field.defaultValue && <SelectItem value="__none__">—</SelectItem>}
                          {(field.options ?? []).map(option => <SelectItem key={option} value={option}>{field.name === "preferred_language" ? languages(option) : field.name === "site_type" ? fieldOptions(`site_type.${option}`) : field.name === "country_code" ? countryLabel(option, locale) : option}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    ) : field.type === "reference" ? (
                      <Select
                        name={field.name}
                        required={field.required}
                        value={String(values[field.name] ?? "")}
                        disabled={!canWrite || busy || refsLoading}
                        onValueChange={(selected) => {
                          if (!canWrite || busy || refsLoading) return;
                          const value = selected === "__none__" ? "" : selected;
                          if (
                            resource.key === "settings" &&
                            field.name === "company_id"
                          ) {
                            setValues((old) => ({
                              ...old,
                              company_id: value,
                              site_id: "",
                            }));
                          } else if (
                            resource.key === "settings" &&
                            field.name === "site_id"
                          ) {
                            const site = refs.sites?.find(
                              (x) => x.id === value,
                            );
                            setValues((old) => ({
                              ...old,
                              site_id: value,
                              ...(site ? { company_id: site.company_id } : {}),
                            }));
                          } else set(field.name, value);
                        }}
                      >
                        <SelectTrigger id={id} className="w-full" aria-label={f(field.name)}><SelectValue placeholder={refsLoading ? t("loading") : "—"} /></SelectTrigger>
                        <SelectContent>
                          {!field.required && <SelectItem value="__none__">—</SelectItem>}
                          {options.map(option => <SelectItem key={option.id} value={option.id}>{rowLabel(option)}{option.is_enabled === false ? ` · ${t("disabled")}` : ""}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    ) : field.type === "textarea" || field.type === "json" ? (
                      <Textarea
                        id={id}
                        required={field.required}
                        value={String(values[field.name] ?? "")}
                        rows={field.type === "json" ? 7 : 3}
                        className={field.type === "json" ? "font-mono" : ""}
                        onChange={(e) => set(field.name, e.target.value)}
                      />
                    ) : (
                      <Input
                        id={id}
                        type={field.type === "date" || field.type === "tel" ? field.type : field.name === "email" ? "email" : "text"}
                        required={fiscalFields && ["vat_number", "tax_code"].includes(field.name) ? !String(values[field.name === "vat_number" ? "tax_code" : "vat_number"] ?? "").trim() : field.required}

                        value={String(values[field.name] ?? "")}
                        autoComplete="off"
                        maxLength={resource.key === "countries" && field.name === "iso_code" ? 2 : undefined}
                        pattern={resource.key === "countries" && field.name === "iso_code" ? "[A-Z]{2}" : undefined}
                        onChange={(e) => set(field.name, field.name === "iso_code" ? e.target.value.toUpperCase() : e.target.value)}
                      />
                    )}
                  </div>
                );
              })}
            </fieldset>
          </form>
          <Notice message={relationsError} />
          <Notice message={coverageError} />
          {resource.key === "roles" && row?.id && can(session, "roles", "read") && can(session, "companies", "read") && <RoleCompanyAccess key={row.id} roleId={row.id} {...{session, scope, onError}} />}
          {coverageVisible && <PurchasingCoverageEditor draft={coverageDraft} editable={coverageEditable} loading={coverageLoading} busy={busy}
            onChange={coverage => {
              if (!coverageEditable || busy || coverageLoading || coverageError) return;
              setCoverageDraft(old => old ? {...old, coverage} : old);
            }} />}
          {visibleRelations.map(relation => <RelationEditor
            key={relation.key}
            relation={relation.key}
            target={relation.target}
            ownerId={row?.id ?? "new"}
            editable={canRelation(session, resource.key, relation.key, "assign", owner)}
            allowedRead
            draft={drafts[relation.key]}
            loading={relationsLoading}
            busy={busy}
            onIdsChange={ids => {
              if (busy || !canRelation(session, resource.key, relation.key, "assign", owner)) return;
              setDrafts(old => old[relation.key] ? {...old, [relation.key]: {...old[relation.key], ids}} : old);
            }}
          />)}
        </div>
        <DialogFooter>
          {!canSave && <span className="read-only">{t("readOnly")}</span>}
          <Button variant="outline" onClick={onClose} disabled={busy}>
            {t("cancel")}
          </Button>
          {canSave && (
            <Button
              type="submit"
              form="record-form"
              disabled={blocked}
            >
              {busy ? t("loading") : t("save")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
type RelationDraft = {options: Row[]; initialIds: string[]; ids: string[]};
function RelationEditor({relation, target, ownerId, editable, allowedRead, draft, loading = false, busy = false, onIdsChange}: {
  relation: string;
  target: string;
  ownerId: string;
  editable: boolean;
  allowedRead: boolean;
  draft?: RelationDraft;
  loading?: boolean;
  busy?: boolean;
  onIdsChange: (ids: string[]) => void;
}) {
  const t = useTranslations("app"), locale = useLocale();
  const [filter, setFilter] = useState("");
  if (!allowedRead) return null;
  const {options = [], ids = []} = draft ?? {};
  const disabled = !editable || busy || loading || !draft;
  const change = (next: string[]) => {if (!disabled) onIdsChange([...new Set(next)]);};
  const visible = options.filter(option => `${rowLabel(option)} ${option.code ?? ""}`.toLowerCase().includes(filter.toLowerCase()));
  const renderOption = (option: Row) => <Label key={option.id} className="relation-option">
    <Checkbox id={`${relation}-${ownerId}-${option.id}`} aria-label={localizedRowLabel(target, option, locale)}
      checked={ids.includes(option.id)} disabled={disabled}
      onCheckedChange={checked => change(checked === true ? [...ids, option.id] : ids.filter(id => id !== option.id))} />
    <span><strong>{localizedRowLabel(target, option, locale)}</strong>{Boolean(option.code) && <small>{String(option.code)}</small>}</span>
    {option.is_enabled === false && <Badge variant="secondary">{t("disabled")}</Badge>}
  </Label>;
  return <section className="relations-section">
    <div className="relation-heading"><h3>{t(relation)}</h3><Badge variant="secondary">{ids.length}</Badge></div>
    <Input aria-label={`${t("search")} ${t(relation)}`} value={filter} placeholder={t("search")} onChange={e => setFilter(e.target.value)} />
    <div className="relation-options" aria-busy={loading}>
      {loading || !draft ? <span>{t("loading")}</span> : relation === "role-permissions" ?
        <PermissionTree rows={options} query={filter} selectedIds={ids} onSelectedIdsChange={change} disabled={disabled} renderLeaf={renderOption} /> :
        visible.length ? visible.map(renderOption) : <p>{t("empty")}</p>}
    </div>
  </section>;
}
function PasswordForm({
  resetId,
  scope = (p) => p,
  onSaved,
  onError,
}: {
  resetId?: string;
  scope?: (p: string) => string;
  onSaved: () => Promise<void>;
  onError: (e: unknown) => string;
}) {
  const t = useTranslations("app");
  const [current, setCurrent] = useState(""),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const validation = passwordValidation(password, confirm);
    if (validation) {
      setError(t(validation));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(
        resetId ? scope(`/users/${resetId}/password`) : "/auth/password",
        "PUT",
        resetId
          ? { newPassword: password }
          : { currentPassword: current, newPassword: password },
      );
      setCurrent("");
      setPassword("");
      setConfirm("");
      await refreshCsrf();
      await onSaved();
    } catch (e) {
      setError(onError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="password-form">
      <Notice message={error} />
      {!resetId && (
        <div className="field">
          <Label htmlFor="current-password">{t("currentPassword")}</Label>
          <Input
            id="current-password"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </div>
      )}
      <div className="field">
        <Label htmlFor="new-password">{t("newPassword")}</Label>
        <Input
          id="new-password"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div className="field">
        <Label htmlFor="confirm-password">{t("confirmPassword")}</Label>
        <Input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>
      <Button type="submit" disabled={busy}>
        {busy ? t("loading") : t("save")}
      </Button>
    </form>
  );
}
