"use client";
import {useEffect, useRef, useState} from "react";
import {useLocale, useTranslations} from "next-intl";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {api} from "@/lib/api";
import {countryLabel} from "@/lib/model";

type Country = {isoCode: string; name: string};
type CountryOptions = {items: Country[]};
export function SiteCountrySelect({id, value, scope, disabled, readOnly = false, required, onChange, "aria-invalid": invalid, "aria-describedby": describedBy}: {
  id: string; value: string; scope: (path: string) => string; disabled: boolean; readOnly?: boolean; required: boolean; onChange: (value: string) => void;
  "aria-invalid"?: boolean; "aria-describedby"?: string;
}) {
  const locale = useLocale(), t = useTranslations("app");
  const [options, setOptions] = useState<CountryOptions>({items: []}),
    [loading, setLoading] = useState(true), [error, setError] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current, controller = new AbortController();
    if (readOnly) {setLoading(false); setError(false); return;}
    setLoading(true); setError(false);
    api<CountryOptions>(scope("/addresses/countries"), "GET", undefined, {signal: controller.signal})
      .then(data => {if (!controller.signal.aborted && current === generation.current) setOptions(data);})
      .catch(() => {if (!controller.signal.aborted && current === generation.current) setError(true);})
      .finally(() => {if (!controller.signal.aborted && current === generation.current) setLoading(false);});
    return () => {controller.abort(); generation.current++;};
  }, [scope, readOnly]);
  // Un paese storico non presente nel catalogo rimane nel draft e nella select.
  const items = value && !options.items.some(item => item.isoCode === value)
    ? [...options.items, {isoCode: value, name: value}] : options.items;
  return <div className="relative">
    <Select name="country_code" value={value} required={required} disabled={disabled || readOnly || loading}
      onValueChange={next => {if (!disabled && !readOnly && !loading) onChange(next === "__none__" ? "" : next);}}>
      <SelectTrigger id={id} className="w-full" aria-busy={loading} aria-invalid={invalid} aria-describedby={[describedBy, error ? `${id}-lookup-error` : undefined].filter(Boolean).join(" ") || undefined}><SelectValue placeholder={loading ? t("loading") : "—"} /></SelectTrigger>
      <SelectContent>
        {!required && <SelectItem value="__none__">—</SelectItem>}
        {items.map(item => <SelectItem key={item.isoCode} value={item.isoCode}>{item.name === item.isoCode ? countryLabel(item.isoCode, locale) : item.name}</SelectItem>)}
      </SelectContent>
    </Select>
    {error && <p id={`${id}-lookup-error`} role="status" className="absolute top-full z-50 mt-1 rounded-md border bg-popover p-2 text-sm text-popover-foreground shadow-md">{t("addressUnavailable")}</p>}
  </div>;
}
